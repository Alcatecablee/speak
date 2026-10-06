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
        self.stage: str = "none"  # "none", "capture", "transcription", "analysis", "ready"
        self.session_id: Optional[str] = None
        self.error_message: Optional[str] = None
        self.start_time: Optional[float] = None

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

    def get_status(self) -> Dict[str, Any]:
        """Returns current engine state and artifact readiness."""
        with self._lock:
            elapsed = time.time() - self.start_time if self.start_time and self.state == "recording" else 0.0
            transcript_json_path = self.output_dir / "transcript.json"
            analysis_json_path = self.output_dir / "analysis.json"
            review_md_path = self.output_dir / "analysis_review.md"
            sf_draft_path = self.output_dir / "salesforce_draft_payload.json"

            return {
                "status": self.state,
                "stage": self.stage,
                "session_id": self.session_id,
                "elapsed_seconds": round(elapsed, 1),
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
            self.error_message = None
            self.start_time = time.time()
            self._capture_stop_event.clear()
            self._q_mic = queue.Queue()
            self._q_loop = queue.Queue()

            try:
                self._pyaudio_instance = pyaudio.PyAudio()
                wasapi_info = self._pyaudio_instance.get_host_api_info_by_type(pyaudio.paWASAPI)
                default_mic = self._pyaudio_instance.get_device_info_by_index(wasapi_info["defaultInputDevice"])
                default_loopback = self._pyaudio_instance.get_default_wasapi_loopback()

                mic_rate = int(default_mic["defaultSampleRate"])
                mic_channels = default_mic["maxInputChannels"]
                loop_rate = int(default_loopback["defaultSampleRate"])
                loop_channels = default_loopback["maxInputChannels"]

                # Remove previous WAV files
                if os.path.exists(self.mic_file):
                    os.remove(self.mic_file)
                if os.path.exists(self.loop_file):
                    os.remove(self.loop_file)

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

                # Start disk writer threads
                t1 = threading.Thread(target=self._disk_writer, args=(self._q_mic, self._f_mic, "MIC"), daemon=True)
                t2 = threading.Thread(target=self._disk_writer, args=(self._q_loop, self._f_loop, "LOOPBACK"), daemon=True)
                t1.start()
                t2.start()
                self._writer_threads = [t1, t2]

                self.state = "recording"
                self.stage = "capture"
                logger.info(f"Capture started successfully (Session: {self.session_id})")

                return {
                    "status": "recording",
                    "stage": "capture",
                    "session_id": self.session_id,
                    "consultant_stream": "active",
                    "client_loopback_stream": "active"
                }
            except Exception as e:
                self.state = "error"
                self.stage = "none"
                self.error_message = f"Failed to start WASAPI capture: {e}"
                logger.error(self.error_message, exc_info=True)
                self._cleanup_streams()
                raise RuntimeError(self.error_message)

    def _disk_writer(self, q: queue.Queue, soundfile_handle: sf.SoundFile, stream_tag: str):
        while not self._capture_stop_event.is_set() or not q.empty():
            try:
                data = q.get(timeout=0.1)
                audio_np = np.frombuffer(data, dtype=np.int16)
                soundfile_handle.write(audio_np)
                q.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.warning(f"Error writing {stream_tag} audio to disk: {e}")
                break

    def stop_capture_and_process(self, skip_stt_demo: bool = False) -> Dict[str, Any]:
        """Stops audio capture and initiates background transcription + analysis."""
        with self._lock:
            if self.state != "recording":
                raise RuntimeError(f"Cannot stop capture when in '{self.state}' state.")

            self.state = "processing"
            self.stage = "transcription"

        # Background processing worker
        threading.Thread(target=self._run_pipeline_worker, args=(skip_stt_demo,), daemon=True).start()

        return {
            "status": "processing",
            "stage": "transcription",
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
            self._cleanup_streams()
            logger.info("Audio capture finalized.")

            transcript_json_path = self.output_dir / "transcript.json"

            # Stage 1: Transcription
            if not skip_stt_demo or not transcript_json_path.exists():
                with self._lock:
                    self.stage = "transcription"
                logger.info("Running transcription pipeline...")
                pipeline = TranscriptionPipeline(model_name=self.whisper_model, output_dir=str(self.output_dir))
                pipeline.process_session(
                    consultant_audio_path=self.mic_file,
                    client_audio_path=self.loop_file
                )
            else:
                logger.info("Using cached transcript for instant processing.")

            # Stage 2: AI Conversation Intelligence
            with self._lock:
                self.stage = "analysis"
            logger.info("Running AI Conversation Intelligence analysis...")
            analyzer = ConversationAnalyzer(provider=GroundedExtractionProvider())
            analyzer.analyze_file(
                transcript_path=str(transcript_json_path),
                output_dir=str(self.output_dir)
            )

            with self._lock:
                self.state = "ready"
                self.stage = "ready"
            logger.info("Session processing completed successfully (State: ready).")

        except Exception as e:
            logger.error(f"Pipeline worker error: {e}", exc_info=True)
            with self._lock:
                self.state = "error"
                self.stage = "none"
                self.error_message = str(e)

    def load_demo_sample(self) -> Dict[str, Any]:
        """Loads pre-analyzed real sample for immediate demonstration."""
        with self._lock:
            transcript_json_path = self.output_dir / "transcript.json"
            if not transcript_json_path.exists():
                raise FileNotFoundError("Sample transcript.json not found.")

            self.session_id = "sample_real_call_demo"
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
                "message": "Demo sample loaded successfully."
            }
