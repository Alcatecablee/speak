import logging
import os
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from transcription.models import TranscriptSegment, MergedTurn
from transcription.merger import merge_speaker_streams, render_transcript_text
from transcription.providers import BaseTranscriptionProvider, get_transcription_provider

logger = logging.getLogger("speak.pipeline")

class TranscriptionPipeline:
    """
    End-to-End pipeline to transcribe two-stream audio (consultant mic + client loopback)
    and produce a unified, timestamped, speaker-labeled dialogue transcript.
    """
    
    def __init__(self, provider: Optional[BaseTranscriptionProvider] = None, provider_type: str = "whisper-hf", **provider_kwargs):
        if provider is not None:
            self.provider = provider
        else:
            self.provider = get_transcription_provider(provider_type, **provider_kwargs)
            
    def process_session(
        self,
        consultant_audio_path: str,
        client_audio_path: str,
        call_start_time: Optional[datetime] = None,
        output_dir: Optional[str] = None,
        stage_callback: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Process both audio streams, merge them, and output transcripts.
        """
        session_start_time = datetime.now()
        call_start = call_start_time or session_start_time
        logger.info(f"=== [TRANSCRIPTION PIPELINE START] ===")
        logger.info(f"Call start timestamp: {call_start.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Consultant Stream: {consultant_audio_path}")
        logger.info(f"Client Stream:     {client_audio_path}")
        
        consultant_segments: List[TranscriptSegment] = []
        client_segments: List[TranscriptSegment] = []
        errors = {}
        
        # 1. Transcribe Consultant Stream
        if stage_callback:
            stage_callback("transcribing_consultant", "Transcribing consultant audio", "Whisper is processing consultant microphone locally on CPU...")
        logger.info("[STREAM 1/2] Beginning transcription of CONSULTANT stream...")
        try:
            consultant_segments = self.provider.transcribe(consultant_audio_path, speaker_label="CONSULTANT")
            logger.info(f"[STREAM 1/2] CONSULTANT transcription completed: {len(consultant_segments)} segments.")
        except Exception as e:
            logger.error(f"[STREAM 1/2] FAILED transcribing CONSULTANT stream: {e}", exc_info=True)
            errors["consultant_error"] = str(e)
            
        # 2. Transcribe Client Stream
        if stage_callback:
            stage_callback("transcribing_client", "Transcribing client audio", "Whisper is processing client audio locally on CPU. This may take a moment...")
        logger.info("[STREAM 2/2] Beginning transcription of CLIENT stream...")
        try:
            client_segments = self.provider.transcribe(client_audio_path, speaker_label="CLIENT")
            logger.info(f"[STREAM 2/2] CLIENT transcription completed: {len(client_segments)} segments.")
        except Exception as e:
            logger.error(f"[STREAM 2/2] FAILED transcribing CLIENT stream: {e}", exc_info=True)
            errors["client_error"] = str(e)
            
        # 3. Merge streams chronologically
        if stage_callback:
            stage_callback("merging_transcript", "Merging speaker transcript", "Aligning timestamps and merging speaker dialogue turns...")
        logger.info("[MERGE] Merging speaker streams by timestamp...")
        merged_turns = merge_speaker_streams(
            consultant_segments=consultant_segments,
            client_segments=client_segments,
            call_start_time=call_start
        )
        logger.info(f"[MERGE] Merge complete: {len(merged_turns)} dialogue turns created.")
        
        # 4. Render human-readable transcript
        transcript_text = render_transcript_text(merged_turns)
        
        # 5. Determine status
        if errors and not (consultant_segments or client_segments):
            status = "failed"
        elif errors:
            status = "partial_success"
        else:
            status = "success"
            
        result = {
            "status": status,
            "call_start_time": call_start.isoformat(),
            "consultant_segments_count": len(consultant_segments),
            "client_segments_count": len(client_segments),
            "total_dialogue_turns": len(merged_turns),
            "merged_turns": [turn.to_dict() for turn in merged_turns],
            "transcript_text": transcript_text,
            "errors": errors,
            "duration_seconds": (datetime.now() - session_start_time).total_seconds()
        }
        
        # 6. Save outputs if output_dir specified
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            txt_path = os.path.join(output_dir, "transcript.txt")
            json_path = os.path.join(output_dir, "transcript.json")
            
            # Atomic write for text transcript
            tmp_txt = os.path.join(output_dir, f"transcript_{os.getpid()}_{int(session_start_time.timestamp())}.tmp")
            with open(tmp_txt, "w", encoding="utf-8") as f:
                f.write(transcript_text)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_txt, txt_path)

            # Atomic write for JSON transcript
            tmp_json = os.path.join(output_dir, f"transcript_json_{os.getpid()}_{int(session_start_time.timestamp())}.tmp")
            with open(tmp_json, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_json, json_path)

            logger.info(f"[OUTPUT] Saved text transcript to: {txt_path}")
            logger.info(f"[OUTPUT] Saved JSON metadata to:  {json_path}")
            
        logger.info(f"=== [TRANSCRIPTION PIPELINE FINISHED: {status.upper()}] ===")
        return result
