import logging
import os
from abc import ABC, abstractmethod
from typing import List, Optional
import numpy as np
import soundfile as sf
from transcription.models import TranscriptSegment

logger = logging.getLogger("speak.transcription")

class BaseTranscriptionProvider(ABC):
    """Abstract interface for speech-to-text engines."""
    
    @abstractmethod
    def transcribe(self, audio_path: str, speaker_label: str = "SPEAKER") -> List[TranscriptSegment]:
        """
        Transcribe the audio file and return a list of timestamped segments.
        Must raise an exception or handle errors gracefully without crashing the pipeline.
        """
        pass

class WhisperHFProvider(BaseTranscriptionProvider):
    """Local Whisper provider using HuggingFace Transformers optimized for multi-core CPU inference."""
    
    def __init__(self, model_name: str = "openai/whisper-tiny", device: Optional[str] = None):
        self.model_name = model_name
        self.device = device
        self._pipeline = None
        
    def _lazy_init(self):
        if self._pipeline is None:
            logger.info(f"Loading Whisper model: {self.model_name}...")
            import torch
            from transformers import pipeline
            
            # Configure multi-threading avoiding hyperthread lock contention
            cpu_cores = min(4, os.cpu_count() or 4)
            torch.set_num_threads(cpu_cores)
            
            if self.device is None:
                self.device = "cuda" if torch.cuda.is_available() else "cpu"
                
            self._pipeline = pipeline(
                "automatic-speech-recognition",
                model=self.model_name,
                device=self.device,
                return_timestamps=True
            )
            logger.info(f"Whisper model {self.model_name} loaded successfully on {self.device} ({cpu_cores} threads).")

    def transcribe(self, audio_path: str, speaker_label: str = "SPEAKER") -> List[TranscriptSegment]:
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
            
        file_size = os.path.getsize(audio_path)
        if file_size < 1000:
            logger.warning(f"Audio file {audio_path} is too small ({file_size} bytes). Skipping.")
            return []
            
        self._lazy_init()
        logger.info(f"Reading audio file ({file_size / (1024*1024):.2f} MB): {audio_path}...")
        
        try:
            # Load raw audio via libsndfile (avoids external ffmpeg requirement)
            audio_data, sample_rate = sf.read(audio_path)
            
            # Convert multi-channel to mono if necessary
            if audio_data.ndim > 1:
                audio_data = audio_data.mean(axis=1)
                
            audio_data = audio_data.astype(np.float32)
            duration_s = len(audio_data) / sample_rate
            logger.info(f"Transcribing {speaker_label} audio ({duration_s:.1f}s, {sample_rate}Hz)...")
            
            # Chunk audio in 30-second windows for fast, non-hallucinating local processing
            chunk_duration = 30.0
            chunk_samples = int(chunk_duration * sample_rate)
            total_samples = len(audio_data)
            
            segments: List[TranscriptSegment] = []
            
            for start_idx in range(0, total_samples, chunk_samples):
                end_idx = min(start_idx + chunk_samples, total_samples)
                chunk_data = audio_data[start_idx:end_idx]
                chunk_start_time = start_idx / sample_rate
                
                # Fast energy check: skip dead silence chunks (energy < threshold)
                rms = np.sqrt(np.mean(chunk_data**2)) if len(chunk_data) > 0 else 0
                if rms < 0.001 and len(chunk_data) == chunk_samples:
                    continue
                    
                input_dict = {"raw": chunk_data, "sampling_rate": sample_rate}
                
                try:
                    result = self._pipeline(
                        input_dict,
                        generate_kwargs={
                            "language": "en",
                            "task": "transcribe",
                            "condition_on_prev_tokens": False
                        }
                    )
                    
                    chunks = result.get("chunks", [])
                    if chunks:
                        for chunk in chunks:
                            ts = chunk.get("timestamp", (0.0, 0.0))
                            rel_start = float(ts[0]) if ts[0] is not None else 0.0
                            rel_end = float(ts[1]) if ts[1] is not None else rel_start + 1.0
                            text = chunk.get("text", "").strip()
                            if text:
                                segments.append(TranscriptSegment(
                                    start_seconds=round(chunk_start_time + rel_start, 2),
                                    end_seconds=round(chunk_start_time + rel_end, 2),
                                    text=text,
                                    speaker=speaker_label
                                ))
                    else:
                        full_text = result.get("text", "").strip()
                        if full_text:
                            segments.append(TranscriptSegment(
                                start_seconds=round(chunk_start_time, 2),
                                end_seconds=round(chunk_start_time + (len(chunk_data) / sample_rate), 2),
                                text=full_text,
                                speaker=speaker_label
                            ))
                except Exception as chunk_err:
                    logger.warning(f"Error transcribing chunk at {chunk_start_time:.1f}s: {chunk_err}")
                    continue
                    
            logger.info(f"Successfully transcribed {speaker_label}: {len(segments)} segments extracted.")
            return segments
            
        except Exception as e:
            logger.error(f"Error during transcription of {audio_path} ({speaker_label}): {e}", exc_info=True)
            raise e

POS_DOMAIN_INITIAL_PROMPT = (
    "Kingpos, MC1, MC2, MC3, POS1, POS2, Adumo, Adumo PED, AnyShop, GRV, GRVs, "
    "MicroSIP, GAAP, GAAP PAY, PAX, Polokwane, Limpopo, SQL Agent service, Back Office, "
    "till rolls, cash-up, receipt printer, butternut puree, stock variance, recipe batch."
)

class FasterWhisperProvider(BaseTranscriptionProvider):
    """High-performance local Whisper provider using CTranslate2 INT8 quantization and Silero VAD."""
    
    def __init__(self, model_size: str = "tiny", device: str = "cpu", compute_type: str = "int8", cpu_threads: Optional[int] = None, initial_prompt: Optional[str] = None):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        # Physical cores default avoids OpenMP thread contention on hyperthreaded CPUs
        self.cpu_threads = cpu_threads or min(4, os.cpu_count() or 4)
        self.initial_prompt = initial_prompt or POS_DOMAIN_INITIAL_PROMPT
        self._model = None
        
    def _lazy_init(self):
        if self._model is None:
            logger.info(f"Loading faster-whisper model '{self.model_size}' ({self.compute_type} on {self.device}, {self.cpu_threads} CPU threads)...")
            from faster_whisper import WhisperModel
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
                cpu_threads=self.cpu_threads
            )
            logger.info("faster-whisper model initialized successfully.")
            
    def transcribe(self, audio_path: str, speaker_label: str = "SPEAKER") -> List[TranscriptSegment]:
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
            
        file_size = os.path.getsize(audio_path)
        if file_size < 1000:
            logger.warning(f"Audio file {audio_path} is too small ({file_size} bytes). Skipping.")
            return []
            
        self._lazy_init()
        logger.info(f"Transcribing {speaker_label} via faster-whisper ({file_size / (1024*1024):.2f} MB): {audio_path}...")
        
        segments_out: List[TranscriptSegment] = []
        try:
            # Silero VAD filters out dead air/silence automatically before Whisper decoding
            segments, info = self._model.transcribe(
                audio_path,
                beam_size=1,
                language="en",
                task="transcribe",
                initial_prompt=self.initial_prompt,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500)
            )
            for seg in segments:
                text = seg.text.strip()
                if text:
                    segments_out.append(TranscriptSegment(
                        start_seconds=round(seg.start, 2),
                        end_seconds=round(seg.end, 2),
                        text=text,
                        speaker=speaker_label
                    ))
            logger.info(f"Successfully transcribed {speaker_label} with faster-whisper: {len(segments_out)} segments extracted.")
            return segments_out
        except Exception as e:
            logger.error(f"Error during faster-whisper transcription of {audio_path} ({speaker_label}): {e}", exc_info=True)
            raise e

class MockTranscriptionProvider(BaseTranscriptionProvider):
    """Deterministic mock provider for offline unit tests and CI."""
    
    def __init__(self, mock_segments: Optional[dict] = None):
        self.mock_segments = mock_segments or {}
        
    def transcribe(self, audio_path: str, speaker_label: str = "SPEAKER") -> List[TranscriptSegment]:
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
            
        logger.info(f"[MockProvider] Transcribing {speaker_label} from {audio_path}")
        if audio_path in self.mock_segments:
            return self.mock_segments[audio_path]
            
        # Default mock segments for testing
        if "mic" in audio_path.lower() or speaker_label == "CONSULTANT":
            return [
                TranscriptSegment(start_seconds=0.5, end_seconds=3.0, text="Good morning, thank you for calling support.", speaker=speaker_label),
                TranscriptSegment(start_seconds=12.0, end_seconds=16.0, text="Let me check the till roll supply policy for your region.", speaker=speaker_label),
                TranscriptSegment(start_seconds=25.0, end_seconds=28.0, text="I have confirmed the details. Is there anything else?", speaker=speaker_label)
            ]
        else:
            return [
                TranscriptSegment(start_seconds=4.0, end_seconds=10.5, text="Hi, we need to order till rolls for our store in Johannesburg.", speaker=speaker_label),
                TranscriptSegment(start_seconds=17.5, end_seconds=23.0, text="Okay great, we need 5 boxes delivered tomorrow.", speaker=speaker_label),
                TranscriptSegment(start_seconds=29.0, end_seconds=31.0, text="No, that is all. Thank you!", speaker=speaker_label)
            ]

def get_transcription_provider(provider_type: Optional[str] = None, **kwargs) -> BaseTranscriptionProvider:
    """Factory to instantiate the configured transcription engine."""
    if provider_type == "mock":
        return MockTranscriptionProvider(**kwargs)
        
    try:
        import faster_whisper
        has_faster_whisper = True
    except ImportError:
        has_faster_whisper = False

    if provider_type == "faster-whisper" or (provider_type in (None, "whisper-hf", "auto") and has_faster_whisper):
        raw_model = kwargs.get("model_size") or kwargs.get("model_name", "tiny")
        model_size = raw_model
        if "whisper-" in model_size:
            model_size = model_size.split("whisper-")[-1]
        if "/" in model_size:
            model_size = model_size.split("/")[-1]
        return FasterWhisperProvider(model_size=model_size)
    elif provider_type == "whisper-hf" or not has_faster_whisper:
        model_name = kwargs.get("model_name", "openai/whisper-tiny")
        return WhisperHFProvider(model_name=model_name)
    else:
        raise ValueError(f"Unknown transcription provider: {provider_type}")
