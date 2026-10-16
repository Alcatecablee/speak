"""
Thread-safe WASAPI audio capture and decoupled session pipeline manager for Speak V2.
Separates hardware audio capture lifecycle from per-session background processing.
Enforces non-destructive session-isolated storage with full UUIDs and atomic persistence.
"""

import hashlib
import json
import logging
import os
from pathlib import Path
import queue
import re
import shutil
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
import uuid

import numpy as np
import pyaudiowpatch as pyaudio
import soundfile as sf

from local_engine.lock import SingleInstanceLock
from transcription.pipeline import TranscriptionPipeline
from intelligence.analyzer import ConversationAnalyzer
from intelligence.providers import GroundedExtractionProvider

logger = logging.getLogger("speak.local_engine")

SESSION_ID_PATTERN = re.compile(r"^(session|demo)_\d{8}_\d{6}_[0-9a-fA-F]{32}$")
EXPECTED_BENCHMARK_SHA256 = "745dcf0225fce11789ea2bd5cf0a3f5348d1bac1163f0f05be65e0534703f141"


def _atomic_replace_with_retry(
    tmp_path: Path,
    file_path: Path,
    max_retries: int = 5,
    initial_delay: float = 0.02
) -> None:
    """
    Replaces file_path with tmp_path atomically.
    Retries transient Windows sharing/access violations (WinError 5 / WinError 32 / PermissionError)
    using bounded exponential backoff. Non-transient errors fail immediately.
    On failure, tmp_path is unlinked safely and original file_path remains intact.
    """
    delay = initial_delay
    last_err: Optional[Exception] = None

    for attempt in range(max_retries):
        try:
            os.replace(tmp_path, file_path)
            return
        except PermissionError as e:
            last_err = e
            if attempt < max_retries - 1:
                time.sleep(delay)
                delay *= 2
            else:
                break
        except OSError as e:
            if getattr(e, "winerror", None) in (5, 32) and attempt < max_retries - 1:
                last_err = e
                time.sleep(delay)
                delay *= 2
            else:
                if tmp_path.exists():
                    try:
                        tmp_path.unlink()
                    except OSError:
                        pass
                raise e

    if tmp_path.exists():
        try:
            tmp_path.unlink()
        except OSError:
            pass
    raise last_err or RuntimeError(f"Atomic replacement failed for {file_path}")


def atomic_write_json(file_path: Path, data: Any, indent: int = 2) -> None:
    """Writes JSON data atomically with file flush, os.fsync, and bounded Windows retry."""
    parent = file_path.parent
    parent.mkdir(parents=True, exist_ok=True)
    tmp_path = parent / f"{file_path.stem}_{uuid.uuid4().hex}.tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent)
            f.flush()
            os.fsync(f.fileno())
        _atomic_replace_with_retry(tmp_path, file_path)
    except Exception as e:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise e


def atomic_write_text(file_path: Path, text: str) -> None:
    """Writes text data atomically with file flush, os.fsync, and bounded Windows retry."""
    parent = file_path.parent
    parent.mkdir(parents=True, exist_ok=True)
    tmp_path = parent / f"{file_path.stem}_{uuid.uuid4().hex}.tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        _atomic_replace_with_retry(tmp_path, file_path)
    except Exception as e:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise e


class SessionManager:
    """
    Manages audio capture lifecycle, bounded session processing queue,
    and session-isolated non-destructive storage.
    """

    def __init__(
        self,
        output_dir: str = "recordings",
        whisper_model: str = "openai/whisper-tiny",
        max_queue_size: int = 16,
        require_instance_lock: bool = False
    ):
        self.output_dir = Path(output_dir).resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.whisper_model = whisper_model
        self.max_queue_size = max_queue_size

        # Multi-instance protection: Single-instance file lock
        self.require_instance_lock = require_instance_lock
        self._single_instance_lock = SingleInstanceLock(self.output_dir)
        if self.require_instance_lock:
            if not self._single_instance_lock.acquire():
                raise RuntimeError(
                    f"Another Speak Local Engine process is already running on '{self.output_dir}'."
                )

        # Hardware audio capture state: IDLE -> STARTING -> RECORDING -> STOPPING -> IDLE
        self.capture_state: str = "idle"
        self.capture_session_id: Optional[str] = None
        self.capture_start_time: Optional[float] = None
        self.capture_error: Optional[str] = None

        # Audio stream handles
        self._pyaudio_instance: Optional[pyaudio.PyAudio] = None
        self._stream_mic = None
        self._stream_loop = None
        self._f_mic: Optional[sf.SoundFile] = None
        self._f_loop: Optional[sf.SoundFile] = None
        self._q_mic: queue.Queue = queue.Queue()
        self._q_loop: queue.Queue = queue.Queue()
        self._capture_stop_event = threading.Event()
        self._writer_threads: list[threading.Thread] = []

        # Synchronization lock
        self._lock = threading.RLock()

        # Active jobs tracking (prevents duplicate enqueuing or concurrent processing)
        self._active_jobs: Set[str] = set()

        # Bounded processing queue & worker lifecycle
        self.processing_queue: queue.Queue = queue.Queue(maxsize=max_queue_size)
        self._worker_thread: Optional[threading.Thread] = None
        self._worker_shutdown_event = threading.Event()

        # Recover interrupted/queued sessions from previous run
        self._recover_startup_sessions()

    # ---------------------------------------------------------------- Worker Lifecycle
    def start_worker(self) -> None:
        """Starts the single-worker background processing thread if not already running."""
        with self._lock:
            if self._worker_thread is None or not self._worker_thread.is_alive():
                self._worker_shutdown_event.clear()
                self._worker_thread = threading.Thread(
                    target=self._queue_worker_loop,
                    name="SpeakProcessingWorker",
                    daemon=True
                )
                self._worker_thread.start()
                logger.info("Session processing worker started.")

    def shutdown_worker(self, timeout: float = 5.0) -> None:
        """Gracefully signals and waits for the worker thread to shut down."""
        with self._lock:
            if self._worker_thread and self._worker_thread.is_alive():
                logger.info("Shutting down session processing worker...")
                self._worker_shutdown_event.set()
                # Put a sentinel None to wake up the worker if waiting
                try:
                    self.processing_queue.put_nowait(None)
                except queue.Full:
                    pass
                self._worker_thread.join(timeout=timeout)
                self._worker_thread = None
                logger.info("Session processing worker shut down cleanly.")
            if self.require_instance_lock:
                self._single_instance_lock.release()

    def _recover_startup_sessions(self) -> None:
        """
        Scans output_dir upon startup.
        Interrupted sessions are durably marked as 'interrupted'.
        Persisted 'queued' and 'queued_backpressure' sessions are re-enqueued for processing.
        """
        if not self.output_dir.exists():
            return

        for entry in self.output_dir.iterdir():
            if not entry.is_dir() or entry.is_symlink():
                continue
            meta_path = entry / "session_metadata.json"
            if not meta_path.exists():
                continue

            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)

                status = meta.get("status")
                if status in ("recording", "stopping", "transcribing", "analysing", "processing"):
                    logger.warning(f"Recovering interrupted session {entry.name}: marking as 'interrupted'")
                    meta["status"] = "interrupted"
                    meta["error_message"] = "Process terminated or system restarted while session was in progress."
                    meta["completed_at"] = datetime.now().isoformat()
                    atomic_write_json(meta_path, meta)

                elif status in ("queued", "queued_backpressure"):
                    mic_path = entry / "consultant_mic.wav"
                    loop_path = entry / "client_loopback.wav"
                    transcript_path = entry / "transcript.json"

                    has_audio = mic_path.exists() and loop_path.exists()
                    has_transcript = transcript_path.exists()
                    if not (has_audio or has_transcript):
                        continue

                    job = {
                        "session_id": entry.name,
                        "session_dir": entry,
                        "session_type": meta.get("session_type", "live"),
                        "mic_path": mic_path,
                        "loop_path": loop_path,
                        "skip_stt": not has_audio and has_transcript
                    }
                    try:
                        self.processing_queue.put_nowait(job)
                        self._active_jobs.add(entry.name)
                        meta["status"] = "queued"
                        atomic_write_json(meta_path, meta)
                        logger.info(f"Re-enqueued session {entry.name} from startup scan.")
                    except queue.Full:
                        meta["status"] = "queued_backpressure"
                        meta["error_message"] = "Queue full on restart recovery. Preserved on disk."
                        atomic_write_json(meta_path, meta)

            except Exception as e:
                logger.warning(f"Error checking session {entry.name} on startup: {e}")

    def _drain_backpressured_sessions(self) -> None:
        """
        Scans disk for sessions in 'queued' or 'queued_backpressure' state
        and automatically enqueues them when queue capacity becomes available.
        Ensures zero stranded recordings without requiring server restart.
        """
        if not self.output_dir.exists():
            return

        with self._lock:
            available_slots = self.max_queue_size - self.processing_queue.qsize()
            if available_slots <= 0:
                return

            for entry in sorted(self.output_dir.iterdir(), key=lambda p: p.stat().st_mtime if p.is_dir() else 0):
                if available_slots <= 0:
                    break
                if not entry.is_dir() or entry.is_symlink():
                    continue
                if not (entry.name.startswith("session_") or entry.name.startswith("demo_")):
                    continue
                if entry.name in self._active_jobs:
                    continue

                meta_path = entry / "session_metadata.json"
                if not meta_path.exists():
                    continue

                try:
                    meta = self._read_metadata(entry)
                    status = meta.get("status")
                    if status in ("queued", "queued_backpressure"):
                        mic_path = entry / "consultant_mic.wav"
                        loop_path = entry / "client_loopback.wav"
                        transcript_path = entry / "transcript.json"

                        has_audio = mic_path.exists() and loop_path.exists()
                        has_transcript = transcript_path.exists()
                        if not (has_audio or has_transcript):
                            continue

                        job = {
                            "session_id": entry.name,
                            "session_dir": entry,
                            "session_type": meta.get("session_type", "live"),
                            "mic_path": mic_path,
                            "loop_path": loop_path,
                            "skip_stt": not has_audio and has_transcript
                        }
                        try:
                            self.processing_queue.put_nowait(job)
                            self._active_jobs.add(entry.name)
                            meta["status"] = "queued"
                            meta["error_message"] = None
                            atomic_write_json(meta_path, meta)
                            available_slots -= 1
                            logger.info(f"Automatically drained backpressured session {entry.name} into queue.")
                        except queue.Full:
                            break
                except Exception as e:
                    logger.warning(f"Error checking backpressured session {entry.name}: {e}")

    # ---------------------------------------------------------------- Validation & Identification
    @staticmethod
    def generate_session_id(prefix: str = "session") -> str:
        """Generates a canonical unique session ID matching SESSION_ID_PATTERN."""
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        full_uuid = uuid.uuid4().hex
        return f"{prefix}_{timestamp_str}_{full_uuid}"

    def validate_session_id(self, session_id: str) -> None:
        """Validates session ID against strict allowlist regex."""
        if not session_id or not isinstance(session_id, str):
            raise ValueError("Session ID must be a non-empty string.")
        if not SESSION_ID_PATTERN.fullmatch(session_id):
            raise ValueError(
                f"Invalid session_id '{session_id}'. Must match pattern: (session|demo)_YYYYMMDD_HHMMSS_<32-hex-uuid>"
            )

    def get_session_dir(self, session_id: str) -> Path:
        """
        Resolves and validates session directory with directory traversal and symlink guards.
        Never returns a fallback directory.
        """
        self.validate_session_id(session_id)
        session_dir = (self.output_dir / session_id).resolve()
        base_dir = self.output_dir.resolve()

        if not session_dir.is_relative_to(base_dir):
            raise ValueError(f"Directory traversal detected for session_id '{session_id}'.")
        if (self.output_dir / session_id).is_symlink():
            raise ValueError(f"Symlinks are disallowed for session_id '{session_id}'.")
        if not session_dir.is_dir():
            raise FileNotFoundError(f"Session '{session_id}' not found.")

        return session_dir

    def _read_metadata(self, session_dir: Path) -> Dict[str, Any]:
        """Reads session metadata JSON."""
        meta_path = session_dir / "session_metadata.json"
        if not meta_path.exists():
            raise FileNotFoundError(f"Session metadata not found in {session_dir.name}")
        with open(meta_path, "r", encoding="utf-8") as f:
            return json.load(f)

    # ---------------------------------------------------------------- Status & Catalog
    def get_status(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Returns capture engine hardware state and, if session_id is provided,
        the status and stage of that specific session.
        """
        with self._lock:
            target_meta = None
            if session_id:
                try:
                    s_dir = self.get_session_dir(session_id)
                    target_meta = self._read_metadata(s_dir)
                except Exception:
                    pass

            if target_meta:
                status = target_meta.get("status", "idle")
                stage = target_meta.get("stage", "none")
                stage_label = target_meta.get("stage_label", "Idle")
                msg = target_meta.get("error_message") or ("Call processing complete" if status == "ready" else "Processing call...")
                sess_id = target_meta.get("session_id")
                sess_type = target_meta.get("session_type", "live")
                elapsed = target_meta.get("elapsed_seconds", 0)
                stages = target_meta.get("completed_stages", [])
                err = target_meta.get("error_message")
                s_dir = self.output_dir / sess_id
                has_t = (s_dir / "transcript.json").exists()
                has_a = (s_dir / "analysis.json").exists()
                has_r = (s_dir / "analysis_review.md").exists()
                has_sf = (s_dir / "salesforce_draft_payload.json").exists()
            elif self.capture_state == "recording":
                status = "recording"
                stage = "recording"
                stage_label = "Recording call"
                msg = "Capturing consultant mic and headset loopback streams..."
                sess_id = self.capture_session_id
                sess_type = "live"
                elapsed = int(time.time() - self.capture_start_time) if self.capture_start_time else 0
                stages = ["recording"]
                err = None
                has_t = has_a = has_r = has_sf = False
            else:
                status = self.capture_state
                stage = "none"
                stage_label = "Idle"
                msg = "Ready for call capture"
                sess_id = None
                sess_type = "none"
                elapsed = 0
                stages = []
                err = self.capture_error
                has_t = has_a = has_r = has_sf = False

            return {
                "status": status,
                "stage": stage,
                "stage_label": stage_label,
                "message": msg,
                "engine_status": self.capture_state,
                "active_recording_session_id": self.capture_session_id,
                "session_id": sess_id,
                "session_type": sess_type,
                "elapsed_seconds": elapsed,
                "completed_stages": stages,
                "queue_size": self.processing_queue.qsize(),
                "error": err,
                "has_transcript": has_t,
                "has_analysis": has_a,
                "has_review": has_r,
                "has_salesforce_draft": has_sf
            }

    def list_sessions(self) -> List[Dict[str, Any]]:
        """
        Enumerates all session directories as the single source of truth.
        Returns live, demo, ready, error, and interrupted sessions.
        """
        sessions = []
        if not self.output_dir.exists():
            return sessions

        for entry in self.output_dir.iterdir():
            if not entry.is_dir() or entry.is_symlink():
                continue
            if not (entry.name.startswith("session_") or entry.name.startswith("demo_")):
                continue

            meta_path = entry / "session_metadata.json"
            if meta_path.exists():
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    sessions.append({
                        "session_id": entry.name,
                        "session_type": meta.get("session_type", "live"),
                        "status": meta.get("status", "unknown"),
                        "stage": meta.get("stage"),
                        "stage_label": meta.get("stage_label"),
                        "created_at": meta.get("created_at"),
                        "completed_at": meta.get("completed_at"),
                        "elapsed_seconds": meta.get("elapsed_seconds", 0),
                        "failed_stage": meta.get("failed_stage"),
                        "error_message": meta.get("error_message"),
                        "audio_available": meta.get("audio_available", False),
                        "has_transcript": (entry / "transcript.json").exists(),
                        "has_analysis": (entry / "analysis.json").exists(),
                        "has_review": (entry / "analysis_review.md").exists(),
                        "has_salesforce_draft": (entry / "salesforce_draft_payload.json").exists(),
                    })
                except Exception as e:
                    sessions.append({
                        "session_id": entry.name,
                        "session_type": "unknown",
                        "status": "corrupted_metadata",
                        "error_message": f"Could not parse metadata: {e}"
                    })
            else:
                sessions.append({
                    "session_id": entry.name,
                    "session_type": "unknown",
                    "status": "missing_metadata",
                    "error_message": "Session metadata file missing"
                })

        # Sort newest first by created_at or session directory name
        sessions.sort(key=lambda s: s.get("created_at") or s.get("session_id", ""), reverse=True)
        return sessions

    # ---------------------------------------------------------------- Capture Lifecycle
    def start_capture(self) -> Dict[str, Any]:
        """
        Acquires audio devices and starts dual-stream WASAPI capture in an isolated session folder.
        Uses exclusive directory creation to guarantee zero collisions.
        """
        with self._lock:
            if self.capture_state in ("starting", "recording", "stopping"):
                raise RuntimeError(f"Capture engine is currently in '{self.capture_state}' state. Cannot start capture.")

            # Generate full UUIDv4 session ID
            session_id = self.generate_session_id(prefix="session")

            session_dir = self.output_dir / session_id
            try:
                # Exclusive directory creation ensures no collision
                os.makedirs(session_dir, exist_ok=False)
            except FileExistsError:
                raise RuntimeError(f"Session directory collision for '{session_id}'.")

            self.capture_state = "starting"
            self.capture_session_id = session_id
            self.capture_start_time = time.time()
            self.capture_error = None
            self._capture_stop_event.clear()
            self._q_mic = queue.Queue()
            self._q_loop = queue.Queue()

            mic_path = session_dir / "consultant_mic.wav"
            loop_path = session_dir / "client_loopback.wav"

            # Initialize initial metadata
            initial_meta = {
                "schema_version": "1.0",
                "session_id": session_id,
                "session_type": "live",
                "status": "recording",
                "stage": "recording",
                "stage_label": "Recording call",
                "created_at": datetime.now().astimezone().isoformat(),
                "recording_started_at": datetime.now().astimezone().isoformat(),
                "recording_stopped_at": None,
                "processing_started_at": None,
                "completed_at": None,
                "elapsed_seconds": 0,
                "completed_stages": ["recording"],
                "failed_stage": None,
                "error_message": None,
                "audio_available": True,
                "artifacts": {
                    "consultant_audio": "consultant_mic.wav",
                    "client_audio": "client_loopback.wav",
                    "transcript_json": "transcript.json",
                    "transcript_txt": "transcript.txt",
                    "analysis_json": "analysis.json",
                    "analysis_review": "analysis_review.md",
                    "salesforce_draft": "salesforce_draft_payload.json",
                    "session_metadata": "session_metadata.json"
                }
            }
            atomic_write_json(session_dir / "session_metadata.json", initial_meta)

            try:
                self._init_audio_hardware(mic_path, loop_path)
                self.capture_state = "recording"
                logger.info(f"Capture started successfully for {session_id}")

                return {
                    "status": "recording",
                    "session_id": session_id,
                    "session_type": "live",
                    "consultant_stream": "active",
                    "client_loopback_stream": "active"
                }

            except Exception as e:
                err_msg = str(e)
                self.capture_state = "error"
                self.capture_error = err_msg
                self._cleanup_streams()

                initial_meta["status"] = "error"
                initial_meta["failed_stage"] = "device_initialization"
                initial_meta["error_message"] = err_msg
                atomic_write_json(session_dir / "session_metadata.json", initial_meta)

                logger.error(f"Failed to start capture: {err_msg}", exc_info=True)
                raise RuntimeError(err_msg)

    def _init_audio_hardware(self, mic_path: Path, loop_path: Path):
        """Initializes PyAudio WASAPI microphone and loopback streams and starts disk writers."""
        self._pyaudio_instance = pyaudio.PyAudio()
        try:
            wasapi_info = self._pyaudio_instance.get_host_api_info_by_type(pyaudio.paWASAPI)
        except Exception:
            raise RuntimeError("Windows WASAPI audio host API is not available on this system.")

        try:
            default_mic = self._pyaudio_instance.get_device_info_by_index(wasapi_info["defaultInputDevice"])
        except Exception:
            raise RuntimeError("No default microphone found for WASAPI audio capture.")

        try:
            default_loopback = self._pyaudio_instance.get_default_wasapi_loopback()
        except Exception:
            raise RuntimeError("No default WASAPI loopback output device found. Ensure speakers or headphones are connected.")

        mic_rate = int(default_mic["defaultSampleRate"])
        mic_channels = default_mic["maxInputChannels"]
        loop_rate = int(default_loopback["defaultSampleRate"])
        loop_channels = default_loopback["maxInputChannels"]

        self._f_mic = sf.SoundFile(str(mic_path), mode='x', samplerate=mic_rate, channels=mic_channels, subtype='PCM_16')
        self._f_loop = sf.SoundFile(str(loop_path), mode='x', samplerate=loop_rate, channels=loop_channels, subtype='PCM_16')

        def mic_cb(in_data, frame_count, time_info, status):
            self._q_mic.put(in_data)
            return (in_data, pyaudio.paContinue)

        def loop_cb(in_data, frame_count, time_info, status):
            self._q_loop.put(in_data)
            return (in_data, pyaudio.paContinue)

        self._stream_mic = self._pyaudio_instance.open(
            format=pyaudio.paInt16,
            channels=mic_channels,
            rate=mic_rate,
            input=True,
            input_device_index=default_mic["index"],
            stream_callback=mic_cb
        )

        self._stream_loop = self._pyaudio_instance.open(
            format=pyaudio.paInt16,
            channels=loop_channels,
            rate=loop_rate,
            input=True,
            input_device_index=default_loopback["index"],
            stream_callback=loop_cb
        )

        self._stream_mic.start_stream()
        self._stream_loop.start_stream()

        t1 = threading.Thread(target=self._disk_writer, args=(self._q_mic, self._f_mic, "MIC", mic_channels), daemon=True)
        t2 = threading.Thread(target=self._disk_writer, args=(self._q_loop, self._f_loop, "LOOPBACK", loop_channels), daemon=True)
        t1.start()
        t2.start()
        self._writer_threads = [t1, t2]

    def _disk_writer(self, q: queue.Queue, soundfile_handle: sf.SoundFile, stream_tag: str, channels: int = 1):
        while not self._capture_stop_event.is_set() or not q.empty():
            try:
                data = q.get(timeout=0.1)
                audio_np = np.frombuffer(data, dtype=np.int16)
                if channels > 1:
                    audio_np = audio_np.reshape(-1, channels)
                soundfile_handle.write(audio_np)
                q.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.warning(f"Error writing {stream_tag} audio to disk: {e}")
                continue

    def _cleanup_streams(self):
        """Signals disk writers, closes WASAPI streams and SoundFile handles safely."""
        self._capture_stop_event.set()
        try:
            if self._stream_mic:
                self._stream_mic.stop_stream()
                self._stream_mic.close()
            if self._stream_loop:
                self._stream_loop.stop_stream()
                self._stream_loop.close()
            if self._pyaudio_instance:
                self._pyaudio_instance.terminate()
        except Exception as e:
            logger.warning(f"Error closing audio streams: {e}")

        for t in self._writer_threads:
            t.join(timeout=1.0)
        self._writer_threads.clear()

        try:
            if self._f_mic and not self._f_mic.closed:
                self._f_mic.close()
            if self._f_loop and not self._f_loop.closed:
                self._f_loop.close()
        except Exception as e:
            logger.warning(f"Error closing soundfiles: {e}")

        self._stream_mic = None
        self._stream_loop = None
        self._pyaudio_instance = None
        self._f_mic = None
        self._f_loop = None

    def stop_capture_and_process(self, session_id: str, skip_stt_demo: bool = False) -> Dict[str, Any]:
        """
        Stops live capture for session_id, flushes buffers, immediately releases audio devices
        back to IDLE, and enqueues the session into the background processing queue.
        """
        with self._lock:
            if not session_id:
                raise ValueError("session_id parameter is required to stop capture.")
            if self.capture_state != "recording":
                raise RuntimeError(f"Cannot stop capture: capture engine is in state '{self.capture_state}'.")
            if session_id != self.capture_session_id:
                raise RuntimeError(
                    f"Session ID '{session_id}' does not match currently active recording '{self.capture_session_id}'."
                )

            session_dir = self.output_dir / session_id
            self.capture_state = "stopping"
            logger.info(f"Stopping audio streams for {session_id} and flushing WAV buffers...")
            self._cleanup_streams()

            elapsed = int(time.time() - self.capture_start_time) if self.capture_start_time else 0
            stopped_time = datetime.now().isoformat()

            # Update session manifest: recording finalized, now queued for background processing
            meta = self._read_metadata(session_dir)
            meta["status"] = "queued"
            meta["stage"] = "queued"
            meta["stage_label"] = "Queued for processing"
            meta["recording_stopped_at"] = stopped_time
            meta["elapsed_seconds"] = elapsed
            meta["completed_stages"] = ["recording", "stopping"]
            atomic_write_json(session_dir / "session_metadata.json", meta)

            # Immediately release capture engine back to IDLE
            self.capture_state = "idle"
            self.capture_session_id = None
            self.capture_start_time = None
            logger.info(f"Audio streams released. Capture engine is IDLE. Enqueuing {session_id} for processing.")

            job = {
                "session_id": session_id,
                "session_dir": session_dir,
                "session_type": "live",
                "mic_path": session_dir / "consultant_mic.wav",
                "loop_path": session_dir / "client_loopback.wav",
                "skip_stt": skip_stt_demo
            }

            # Enqueue with bounded backpressure handling
            try:
                self.processing_queue.put(job, block=True, timeout=0.1)
                self._active_jobs.add(session_id)
                queue_status = "queued"
                msg = "Audio capture finalized. Background processing queued."
            except queue.Full:
                meta["status"] = "queued_backpressure"
                meta["error_message"] = "Processing queue is full. Audio is preserved safely on disk and will be processed when a slot opens."
                atomic_write_json(session_dir / "session_metadata.json", meta)
                queue_status = "queued_backpressure"
                msg = "Audio capture saved safely. Background processing queued under backpressure."

            # Ensure background worker thread is active
            self.start_worker()

            return {
                "status": queue_status,
                "session_id": session_id,
                "message": msg
            }

    # ---------------------------------------------------------------- Background Worker
    def _queue_worker_loop(self):
        """Single-worker consumer thread processing queued sessions one by one."""
        logger.info("Processing worker loop started.")
        while not self._worker_shutdown_event.is_set():
            try:
                job = self.processing_queue.get(timeout=0.5)
            except queue.Empty:
                self._drain_backpressured_sessions()
                continue

            if job is None or self._worker_shutdown_event.is_set():
                break

            session_id = job["session_id"]
            session_dir = job["session_dir"]
            session_type = job["session_type"]

            try:
                self._process_single_session(job)
            except Exception as e:
                logger.error(f"Error processing session {session_id}: {e}", exc_info=True)
                try:
                    meta = self._read_metadata(session_dir)
                    meta["status"] = "error"
                    meta["error_message"] = str(e)
                    meta["completed_at"] = datetime.now().isoformat()
                    atomic_write_json(session_dir / "session_metadata.json", meta)
                except Exception as meta_err:
                    logger.error(f"Failed to record error metadata for {session_id}: {meta_err}")
            finally:
                with self._lock:
                    self._active_jobs.discard(session_id)
                    self._drain_backpressured_sessions()
                self.processing_queue.task_done()

        logger.info("Processing worker loop terminated.")

    def _process_single_session(self, job: Dict[str, Any]):
        """Executes Stage 1 (STT) and Stage 2 (Intelligence) for a single session."""
        session_id = job["session_id"]
        session_dir = job["session_dir"]
        session_type = job["session_type"]
        mic_path = job["mic_path"]
        loop_path = job["loop_path"]
        skip_stt = job.get("skip_stt", False)

        meta = self._read_metadata(session_dir)
        meta["status"] = "processing"
        meta["processing_started_at"] = datetime.now().isoformat()
        atomic_write_json(session_dir / "session_metadata.json", meta)

        transcript_json_path = session_dir / "transcript.json"

        # Stage 1: Transcription
        if not skip_stt or not transcript_json_path.exists():
            meta["stage"] = "transcribing_consultant"
            meta["stage_label"] = "Transcribing audio"
            atomic_write_json(session_dir / "session_metadata.json", meta)

            logger.info(f"[{session_id}] Running Whisper transcription on CPU...")
            call_start_str = meta.get("recording_started_at")
            call_start_dt = None
            if call_start_str:
                try:
                    call_start_dt = datetime.fromisoformat(call_start_str)
                except Exception:
                    call_start_dt = None

            pipeline = TranscriptionPipeline(model_name=self.whisper_model)
            pipeline.process_session(
                consultant_audio_path=str(mic_path),
                client_audio_path=str(loop_path),
                output_dir=str(session_dir),
                call_start_time=call_start_dt
            )

        # Stage 2: AI Conversation Intelligence
        meta["stage"] = "analysing"
        meta["stage_label"] = "Analyzing conversation"
        if "transcribing_consultant" not in meta.get("completed_stages", []):
            meta.setdefault("completed_stages", []).extend(["transcribing_consultant", "transcribing_client", "merging_transcript"])
        atomic_write_json(session_dir / "session_metadata.json", meta)

        logger.info(f"[{session_id}] Running Conversation Intelligence analysis...")
        analyzer = ConversationAnalyzer(provider=GroundedExtractionProvider())
        analyzer.analyze_file(
            transcript_path=str(transcript_json_path),
            output_dir=str(session_dir)
        )

        # Finalize
        meta["status"] = "ready"
        meta["stage"] = "ready"
        meta["stage_label"] = "Processing complete"
        meta["completed_at"] = datetime.now().isoformat()
        meta.setdefault("completed_stages", []).extend(["analysing", "preparing_review"])
        atomic_write_json(session_dir / "session_metadata.json", meta)
        logger.info(f"[{session_id}] Processing complete. Artifacts ready.")

    # ---------------------------------------------------------------- Demo Sample Loading
    def load_demo_sample(self) -> Dict[str, Any]:
        """
        Loads pre-analyzed benchmark sample into a unique isolated demo session folder.
        Reads from immutable benchmark fixture without modifying it.
        Outputs exactly 6 artifacts (no audio fabricated).
        """
        candidate_paths = [
            Path("fixtures/demo_sample_transcript.json"),
            Path("tests/fixtures/benchmark_session/transcript.json"),
            Path("recordings_preserved/demo_sample_transcript.json"),
        ]
        sample_source = None
        for cp in candidate_paths:
            if cp.exists():
                sample_source = cp
                break

        if not sample_source:
            raise FileNotFoundError("Demo fixture demo_sample_transcript.json not found in fixtures/ or fallback paths.")

        # Verify fixture SHA-256 integrity
        try:
            fixture_hash = hashlib.sha256(sample_source.read_bytes()).hexdigest()
            if fixture_hash != EXPECTED_BENCHMARK_SHA256:
                logger.warning(
                    f"Benchmark fixture {sample_source} SHA-256 ({fixture_hash}) differs from expected ({EXPECTED_BENCHMARK_SHA256})"
                )
        except Exception as hash_err:
            logger.warning(f"Could not compute fixture SHA-256: {hash_err}")

        demo_id = self.generate_session_id(prefix="demo")
        demo_dir = self.output_dir / demo_id
        os.makedirs(demo_dir, exist_ok=False)

        # Copy fixture to isolated demo directory
        dest_transcript = demo_dir / "transcript.json"
        shutil.copyfile(sample_source, dest_transcript)

        # Generate transcript.txt formatted text from JSON turns
        try:
            with open(sample_source, "r", encoding="utf-8") as f:
                t_json = json.load(f)
            t_lines = [f"[{t.get('speaker', 'SPEAKER')}]: {t.get('text', '')}" for t in t_json.get("merged_turns", [])]
            atomic_write_text(demo_dir / "transcript.txt", "\n".join(t_lines) + "\n")
        except Exception as e:
            logger.warning(f"Could not generate transcript.txt for demo: {e}")

        # Write initial demo metadata (audio_available: false)
        meta = {
            "schema_version": "1.0",
            "session_id": demo_id,
            "session_type": "demo",
            "status": "processing",
            "stage": "analysing",
            "stage_label": "Analyzing demo conversation",
            "created_at": datetime.now().isoformat(),
            "recording_started_at": None,
            "recording_stopped_at": None,
            "processing_started_at": datetime.now().isoformat(),
            "completed_at": None,
            "elapsed_seconds": 555,
            "completed_stages": ["merging_transcript"],
            "failed_stage": None,
            "error_message": None,
            "audio_available": False,
            "artifacts": {
                "transcript_json": "transcript.json",
                "transcript_txt": "transcript.txt",
                "analysis_json": "analysis.json",
                "analysis_review": "analysis_review.md",
                "salesforce_draft": "salesforce_draft_payload.json",
                "session_metadata": "session_metadata.json"
            }
        }
        atomic_write_json(demo_dir / "session_metadata.json", meta)

        # Run analysis synchronously for instant demo experience
        analyzer = ConversationAnalyzer(provider=GroundedExtractionProvider())
        analyzer.analyze_file(
            transcript_path=str(dest_transcript),
            output_dir=str(demo_dir)
        )

        meta["status"] = "ready"
        meta["stage"] = "ready"
        meta["stage_label"] = "Demo ready"
        meta["completed_at"] = datetime.now().isoformat()
        meta["completed_stages"].extend(["analysing", "preparing_review"])
        atomic_write_json(demo_dir / "session_metadata.json", meta)

        logger.info(f"Loaded demo session successfully: {demo_id}")
        return {
            "status": "ready",
            "session_id": demo_id,
            "session_type": "demo",
            "message": "Demo sample loaded successfully."
        }

    # ---------------------------------------------------------------- Data Retrieval
    def get_transcript_data(self, session_id: str) -> Dict[str, Any]:
        """Returns transcript JSON and plain text for session_id. Requires explicit session_id."""
        if not session_id:
            raise ValueError("session_id parameter is required.")
        session_dir = self.get_session_dir(session_id)
        meta = self._read_metadata(session_dir)

        if meta.get("status") in ("queued", "processing", "transcribing", "stopping"):
            raise RuntimeError(f"Session '{session_id}' is currently {meta.get('status')}. Artifacts are not ready.")

        json_path = session_dir / "transcript.json"
        txt_path = session_dir / "transcript.txt"

        if not json_path.exists():
            raise FileNotFoundError(f"Transcript artifact not found for session '{session_id}'.")

        with open(json_path, "r", encoding="utf-8") as f:
            transcript_json = json.load(f)

        raw_text = txt_path.read_text(encoding="utf-8") if txt_path.exists() else ""

        return {
            "status": "success",
            "session_id": session_id,
            "session_type": meta.get("session_type", "live"),
            "data": transcript_json,
            "formatted_text": raw_text
        }

    def get_analysis_data(self, session_id: str) -> Dict[str, Any]:
        """Returns structured analysis JSON for session_id. Requires explicit session_id."""
        if not session_id:
            raise ValueError("session_id parameter is required.")
        session_dir = self.get_session_dir(session_id)
        meta = self._read_metadata(session_dir)

        if meta.get("status") in ("queued", "processing", "transcribing", "stopping"):
            raise RuntimeError(f"Session '{session_id}' is currently {meta.get('status')}. Artifacts are not ready.")

        analysis_path = session_dir / "analysis.json"
        if not analysis_path.exists():
            raise FileNotFoundError(f"Analysis artifact not found for session '{session_id}'.")

        with open(analysis_path, "r", encoding="utf-8") as f:
            analysis_json = json.load(f)

        return {
            "status": "success",
            "session_id": session_id,
            "session_type": meta.get("session_type", "live"),
            "data": analysis_json
        }

    def get_review_data(self, session_id: str) -> Dict[str, Any]:
        """Returns review markdown and draft Salesforce payload for session_id. Requires explicit session_id."""
        if not session_id:
            raise ValueError("session_id parameter is required.")
        session_dir = self.get_session_dir(session_id)
        meta = self._read_metadata(session_dir)

        if meta.get("status") in ("queued", "processing", "transcribing", "stopping"):
            raise RuntimeError(f"Session '{session_id}' is currently {meta.get('status')}. Artifacts are not ready.")

        review_path = session_dir / "analysis_review.md"
        sf_path = session_dir / "salesforce_draft_payload.json"

        if not review_path.exists():
            raise FileNotFoundError(f"Review artifact not found for session '{session_id}'.")

        markdown_text = review_path.read_text(encoding="utf-8")
        sf_payload = {}
        if sf_path.exists():
            with open(sf_path, "r", encoding="utf-8") as f:
                sf_payload = json.load(f)

        return {
            "status": "success",
            "session_id": session_id,
            "session_type": meta.get("session_type", "live"),
            "markdown": markdown_text,
            "salesforce_draft": sf_payload
        }

    def retry_session(self, session_id: str) -> Dict[str, Any]:
        """
        Manually re-enqueues an interrupted, errored, or backpressured session.
        Validates session existence, input artifacts (audio or transcript), and status eligibility.
        Guards against duplicate concurrent processing using self._active_jobs.
        """
        self.validate_session_id(session_id)
        session_dir = self.get_session_dir(session_id)

        with self._lock:
            if session_id in self._active_jobs:
                raise RuntimeError(
                    f"Session '{session_id}' is already currently enqueued or being processed."
                )

            meta = self._read_metadata(session_dir)
            current_status = meta.get("status")

            # Check eligibility: only error, interrupted, or queued_backpressure can be retried
            eligible_statuses = ("error", "interrupted", "queued_backpressure")
            if current_status not in eligible_statuses:
                raise RuntimeError(
                    f"Session '{session_id}' is in status '{current_status}' and cannot be retried. "
                    f"Eligible statuses for retry are: {', '.join(eligible_statuses)}."
                )

            # Validate input artifacts
            mic_path = session_dir / "consultant_mic.wav"
            loop_path = session_dir / "client_loopback.wav"
            transcript_path = session_dir / "transcript.json"

            has_audio = mic_path.exists() and loop_path.exists()
            has_transcript = transcript_path.exists()

            if not (has_audio or has_transcript):
                raise FileNotFoundError(
                    f"Session '{session_id}' cannot be retried: neither audio recordings nor transcript artifacts exist."
                )

            job = {
                "session_id": session_id,
                "session_dir": session_dir,
                "session_type": meta.get("session_type", "live"),
                "mic_path": mic_path,
                "loop_path": loop_path,
                "skip_stt": not has_audio and has_transcript
            }

            try:
                self.processing_queue.put(job, block=True, timeout=0.1)
                self._active_jobs.add(session_id)
                meta["status"] = "queued"
                meta["stage"] = "queued"
                meta["stage_label"] = "Queued for retry"
                meta["error_message"] = None
                meta["failed_stage"] = None
                meta["retried_at"] = datetime.now().isoformat()
                atomic_write_json(session_dir / "session_metadata.json", meta)
                self.start_worker()
                logger.info(f"Session {session_id} successfully queued for retry.")
                return {
                    "status": "queued",
                    "session_id": session_id,
                    "message": "Session successfully queued for retry processing."
                }
            except queue.Full:
                meta["status"] = "queued_backpressure"
                meta["stage"] = "queued_backpressure"
                meta["stage_label"] = "Queued under backpressure"
                meta["error_message"] = "Processing queue is full. Session will be processed automatically when a worker slot opens."
                meta["failed_stage"] = None
                meta["retried_at"] = datetime.now().isoformat()
                atomic_write_json(session_dir / "session_metadata.json", meta)
                self.start_worker()
                logger.warning(f"Processing queue full: session {session_id} retried under backpressure.")
                return {
                    "status": "queued_backpressure",
                    "session_id": session_id,
                    "message": "Processing queue is full. Session queued under backpressure and will be processed automatically."
                }

