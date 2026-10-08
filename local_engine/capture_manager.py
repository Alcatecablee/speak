"""
Thread-safe WASAPI audio capture and pipeline session manager for Speak V2.
Coordinates background dual-stream recording and post-call processing (STT + AI Analysis).
"""

import json
import logging
import os
import queue
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
import uuid

import numpy as np
import pyaudiowpatch as pyaudio
import soundfile as sf

from transcription.pipeline import TranscriptionPipeline
from intelligence.analyzer import ConversationAnalyzer
from intelligence.providers import GroundedExtractionProvider

logger = logging.getLogger("speak.local_engine")


class SessionManager:
    """Manages recording state, WASAPI capture threads, and post-call pipeline execution."""

    def __init__(self, output_dir: str = "recordings", whisper_model: str = "openai/whisper-tiny"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.whisper_model = whisper_model

        self.state: str = "idle"  # "idle", "recording", "processing", "ready", "error"
        self.stage: str = "none"  # "stopping", "transcribing_consultant", "transcribing_client", "merging_transcript", "analysing", "preparing_review", "ready", "error"
        self.stage_label: str = "Idle"
        self.message: str = "Ready for call capture"
        self.session_id: Optional[str] = None
        self.session_type: str = "none"  # "live", "demo", "none"
        self._active_session_data: Dict[str, Any] = {}
        self.error_message: Optional[str] = None
        self.start_time: Optional[float] = None
        self.processing_start_time: Optional[float] = None
        self.completed_stages: list[str] = []

        self._pyaudio_instance: Optional[pyaudio.PyAudio] = None
        self._stream_mic = None
        self._stream_loop = None
        self._f_mic: Optional[sf.SoundFile] = None
        self._f_loop: Optional[sf.SoundFile] = None
        self._q_mic: queue.Queue = queue.Queue()
        self._q_loop: queue.Queue = queue.Queue()
        self._capture_stop_event = threading.Event()
        self._writer_threads: list[threading.Thread] = []
        self._lock = threading.Lock()

        self.mic_file = "consultant_mic.wav"
        self.loop_file = "client_loopback.wav"

    def _update_stage(self, stage: str, stage_label: str, message: str):
        """Thread-safe stage update recording completed milestones."""
        with self._lock:
            if self.stage not in ("none", "idle", "recording", stage) and self.stage not in self.completed_stages:
                self.completed_stages.append(self.stage)
            self.stage = stage
            self.stage_label = stage_label
            self.message = message
            logger.info(f"[STAGE: {stage}] {stage_label} - {message}")

    def get_status(self) -> Dict[str, Any]:
        """Returns current engine state, detailed processing progress, and artifact readiness."""
        with self._lock:
            if self.state == "recording":
                elapsed = time.time() - self.start_time if self.start_time else 0.0
            elif self.state == "processing":
                elapsed = time.time() - self.processing_start_time if self.processing_start_time else 0.0
            else:
                elapsed = 0.0

            transcript_json_path = self.output_dir / "transcript.json"
            analysis_json_path = self.output_dir / "analysis.json"
            review_md_path = self.output_dir / "analysis_review.md"
            sf_draft_path = self.output_dir / "salesforce_draft_payload.json"

            return {
                "status": self.state,
                "stage": self.stage,
                "stage_label": self.stage_label,
                "message": self.message,
                "started_at": datetime.fromtimestamp(self.processing_start_time).isoformat() if self.processing_start_time else None,
                "elapsed_seconds": int(elapsed),
                "completed_stages": list(self.completed_stages),
                "session_id": self.session_id,
                "session_type": self.session_type,
                "error": self.error_message,
                "has_transcript": transcript_json_path.exists(),
                "has_analysis": analysis_json_path.exists(),
                "has_review": review_md_path.exists(),
                "has_salesforce_draft": sf_draft_path.exists(),
            }

    def start_capture(self) -> Dict[str, Any]:
        """Initiates WASAPI capture on consultant mic and client loopback."""
        with self._lock:
            if self.state in ("recording", "processing"):
                raise RuntimeError(f"Engine is already in '{self.state}' state.")

            self.session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
            self.session_type = "live"
            self._active_session_data = {"session_id": self.session_id, "session_type": "live"}
            self.error_message = None
            self.start_time = time.time()
            self.processing_start_time = None
            self.completed_stages = []
            self._capture_stop_event.clear()
            self._q_mic = queue.Queue()
            self._q_loop = queue.Queue()

            try:
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

                # Remove previous WAV files and session artifacts
                if os.path.exists(self.mic_file):
                    os.remove(self.mic_file)
                if os.path.exists(self.loop_file):
                    os.remove(self.loop_file)

                for artifact_name in ("transcript.json", "transcript.txt", "analysis.json", "analysis_review.md", "salesforce_draft_payload.json"):
                    p = self.output_dir / artifact_name
                    if p.exists():
                        try:
                            p.unlink()
                        except Exception:
                            pass

                self._f_mic = sf.SoundFile(self.mic_file, mode='x', samplerate=mic_rate, channels=mic_channels, subtype='PCM_16')
                self._f_loop = sf.SoundFile(self.loop_file, mode='x', samplerate=loop_rate, channels=loop_channels, subtype='PCM_16')

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

                # Start disk writer threads
                t1 = threading.Thread(target=self._disk_writer, args=(self._q_mic, self._f_mic, "MIC", mic_channels), daemon=True)
                t2 = threading.Thread(target=self._disk_writer, args=(self._q_loop, self._f_loop, "LOOPBACK", loop_channels), daemon=True)
                t1.start()
                t2.start()
                self._writer_threads = [t1, t2]

                self.state = "recording"
                self.stage = "recording"
                self.stage_label = "Recording call"
                self.message = "Capturing consultant mic and headset loopback streams..."
                logger.info(f"Capture started successfully (Session: {self.session_id})")

                return {
                    "status": "recording",
                    "stage": "recording",
                    "stage_label": self.stage_label,
                    "message": self.message,
                    "session_id": self.session_id,
                    "consultant_stream": "active",
                    "client_loopback_stream": "active"
                }
            except Exception as e:
                self.state = "error"
                self.stage = "none"
                self.stage_label = "Capture failed"
                err_str = str(e)
                if "WASAPI" in err_str or "microphone" in err_str.lower() or "device" in err_str.lower():
                    self.error_message = f"Audio device error: {err_str}"
                else:
                    self.error_message = f"Failed to start audio capture: {err_str}"
                logger.error(self.error_message, exc_info=True)
                self._cleanup_streams()
                raise RuntimeError(self.error_message)

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

    def stop_capture_and_process(self, skip_stt_demo: bool = False) -> Dict[str, Any]:
        """Stops audio capture and initiates background transcription + analysis."""
        with self._lock:
            if self.state != "recording":
                raise RuntimeError(f"Cannot stop capture when in '{self.state}' state.")

            self.state = "processing"
            self.stage = "stopping"
            self.stage_label = "Finalizing audio capture"
            self.message = "Flushing WAV audio buffers to disk..."
            self.processing_start_time = time.time()
            self.completed_stages = ["recording"]

        # Background processing worker
        threading.Thread(target=self._run_pipeline_worker, args=(skip_stt_demo,), daemon=True).start()

        return {
            "status": "processing",
            "stage": self.stage,
            "stage_label": self.stage_label,
            "message": self.message,
            "session_id": self.session_id
        }

    def _cleanup_streams(self):
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
            logger.warning(f"Error cleaning streams: {e}")

        for t in self._writer_threads:
            t.join(timeout=1.0)

        try:
            if self._f_mic and not self._f_mic.closed:
                self._f_mic.close()
            if self._f_loop and not self._f_loop.closed:
                self._f_loop.close()
        except Exception as e:
            logger.warning(f"Error closing soundfiles: {e}")

    def _run_pipeline_worker(self, skip_stt_demo: bool = False):
        try:
            logger.info("Stopping audio streams and flushing WAV buffers...")
            self._update_stage("stopping", "Finalizing audio capture", "Stopping streams and flushing WAV buffers...")
            self._cleanup_streams()
            logger.info("Audio capture finalized.")

            transcript_json_path = self.output_dir / "transcript.json"

            # Stage 1: Transcription
            if not skip_stt_demo or not transcript_json_path.exists():
                self._update_stage("transcribing_consultant", "Transcribing consultant audio", "Whisper is processing consultant microphone on CPU...")
                logger.info("Running transcription pipeline...")
                pipeline = TranscriptionPipeline(model_name=self.whisper_model)
                pipeline.process_session(
                    consultant_audio_path=self.mic_file,
                    client_audio_path=self.loop_file,
                    output_dir=str(self.output_dir),
                    stage_callback=self._update_stage
                )
            else:
                logger.info("Using cached transcript for instant processing.")

            # Stage 2: AI Conversation Intelligence
            self._update_stage("analysing", "Analyzing conversation", "Extracting verified facts, commitments, and sentiment...")
            logger.info("Running AI Conversation Intelligence analysis...")
            analyzer = ConversationAnalyzer(provider=GroundedExtractionProvider())
            analyzer.analyze_file(
                transcript_path=str(transcript_json_path),
                output_dir=str(self.output_dir)
            )

            # Stage 3: Preparing Salesforce Draft
            self._update_stage("preparing_review", "Preparing Salesforce draft", "Formatting draft case payload and review boundary...")

            with self._lock:
                if self.stage not in self.completed_stages:
                    self.completed_stages.append(self.stage)
                self.state = "ready"
                self.stage = "ready"
                self.stage_label = "Processing complete"
                self.message = "Call transcript, intelligence analysis, and Salesforce draft are ready."
            logger.info("Session processing completed successfully (State: ready).")

        except Exception as e:
            logger.error(f"Pipeline worker error: {e}", exc_info=True)
            with self._lock:
                self.state = "error"
                self.stage = "error"
                self.stage_label = "Processing failed"
                self.message = str(e)
                self.error_message = f"Processing error: {str(e)}"

    def load_demo_sample(self) -> Dict[str, Any]:
        """Loads pre-analyzed real sample for immediate demonstration."""
        with self._lock:
            sample_source = self.output_dir / "demo_sample_transcript.json"
            transcript_json_path = self.output_dir / "transcript.json"

            if sample_source.exists():
                import shutil
                shutil.copyfile(sample_source, transcript_json_path)
            elif not transcript_json_path.exists():
                raise FileNotFoundError("Sample transcript.json not found.")

            self.session_id = "sample_real_call_demo"
            self.session_type = "demo"
            self._active_session_data = {"session_id": self.session_id, "session_type": "demo"}
            self.state = "ready"
            self.stage = "ready"
            self.error_message = None

            analyzer = ConversationAnalyzer(provider=GroundedExtractionProvider())
            analyzer.analyze_file(
                transcript_path=str(transcript_json_path),
                output_dir=str(self.output_dir)
            )

            return {
                "status": "ready",
                "stage": "ready",
                "session_id": self.session_id,
                "session_type": "demo",
                "message": "Demo sample loaded successfully."
            }

    def get_transcript_data(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Returns transcript for the active session, validating session_id if provided."""
        with self._lock:
            if session_id and self.session_id and session_id != self.session_id:
                raise KeyError(f"Requested session '{session_id}' does not match active session '{self.session_id}'.")

            json_path = self.output_dir / "transcript.json"
            txt_path = self.output_dir / "transcript.txt"

            if not json_path.exists():
                raise FileNotFoundError("No transcript found. Record a call first.")

            with open(json_path, "r", encoding="utf-8") as f:
                transcript_json = json.load(f)

            raw_text = txt_path.read_text(encoding="utf-8") if txt_path.exists() else ""

            return {
                "status": "success",
                "session_id": self.session_id,
                "session_type": self.session_type,
                "data": transcript_json,
                "formatted_text": raw_text
            }

    def get_analysis_data(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Returns analysis JSON for the active session, validating session_id if provided."""
        with self._lock:
            if session_id and self.session_id and session_id != self.session_id:
                raise KeyError(f"Requested session '{session_id}' does not match active session '{self.session_id}'.")

            analysis_path = self.output_dir / "analysis.json"
            if not analysis_path.exists():
                raise FileNotFoundError("No analysis found. Record a call first.")

            with open(analysis_path, "r", encoding="utf-8") as f:
                analysis_json = json.load(f)

            return {
                "status": "success",
                "session_id": self.session_id,
                "session_type": self.session_type,
                "data": analysis_json
            }

    def get_review_data(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Returns review markdown and draft Salesforce payload for the active session."""
        with self._lock:
            if session_id and self.session_id and session_id != self.session_id:
                raise KeyError(f"Requested session '{session_id}' does not match active session '{self.session_id}'.")

            review_path = self.output_dir / "analysis_review.md"
            sf_path = self.output_dir / "salesforce_draft_payload.json"

            if not review_path.exists():
                raise FileNotFoundError("No review document found. Record a call first.")

            markdown_text = review_path.read_text(encoding="utf-8")

            sf_payload = {}
            if sf_path.exists():
                with open(sf_path, "r", encoding="utf-8") as f:
                    sf_payload = json.load(f)

            return {
                "status": "success",
                "session_id": self.session_id,
                "session_type": self.session_type,
                "markdown": markdown_text,
                "salesforce_draft": sf_payload
            }
