"""
Speak Your Notes - Two-Stream Transcription Pipeline
"""
from transcription.models import TranscriptSegment, MergedTurn
from transcription.merger import merge_speaker_streams, render_transcript_text
from transcription.providers import BaseTranscriptionProvider, WhisperHFProvider, MockTranscriptionProvider, get_transcription_provider
from transcription.pipeline import TranscriptionPipeline

__all__ = [
    "TranscriptSegment",
    "MergedTurn",
    "merge_speaker_streams",
    "render_transcript_text",
    "BaseTranscriptionProvider",
    "WhisperHFProvider",
    "MockTranscriptionProvider",
    "get_transcription_provider",
    "TranscriptionPipeline",
]
