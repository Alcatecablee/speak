import unittest
import os
import shutil
import tempfile
import json
from datetime import datetime
from transcription.models import TranscriptSegment, MergedTurn
from transcription.merger import merge_speaker_streams, render_transcript_text, format_timestamp
from transcription.providers import MockTranscriptionProvider, get_transcription_provider
from transcription.pipeline import TranscriptionPipeline

class TestTranscriptionDataModels(unittest.TestCase):
    def test_segment_to_dict(self):
        seg = TranscriptSegment(start_seconds=1.2, end_seconds=3.4, text="Hello", speaker="CONSULTANT", confidence=0.95)
        d = seg.to_dict()
        self.assertEqual(d["start_seconds"], 1.2)
        self.assertEqual(d["speaker"], "CONSULTANT")
        self.assertEqual(d["text"], "Hello")

    def test_merged_turn_formatting(self):
        turn = MergedTurn(speaker="CLIENT", start_seconds=5.0, end_seconds=8.0, timestamp_str="10:00:05", text="I have an issue.")
        self.assertEqual(turn.formatted_line(), "[10:00:05] CLIENT: I have an issue.")

class TestStreamMerger(unittest.TestCase):
    def test_chronological_merge_and_labeling(self):
        consultant = [
            TranscriptSegment(start_seconds=0.0, end_seconds=2.0, text="Hello, support here.", speaker="CONSULTANT"),
            TranscriptSegment(start_seconds=7.0, end_seconds=10.0, text="Let me check that for you.", speaker="CONSULTANT"),
        ]
        client = [
            TranscriptSegment(start_seconds=2.5, end_seconds=6.5, text="My printer is offline.", speaker="CLIENT"),
            TranscriptSegment(start_seconds=11.0, end_seconds=14.0, text="Thank you.", speaker="CLIENT"),
        ]
        
        start_time = datetime(2026, 10, 6, 10, 0, 0)
        turns = merge_speaker_streams(consultant, client, call_start_time=start_time)
        
        self.assertEqual(len(turns), 4)
        self.assertEqual(turns[0].speaker, "CONSULTANT")
        self.assertEqual(turns[0].text, "Hello, support here.")
        self.assertEqual(turns[0].timestamp_str, "10:00:00")
        
        self.assertEqual(turns[1].speaker, "CLIENT")
        self.assertEqual(turns[1].text, "My printer is offline.")
        self.assertEqual(turns[1].timestamp_str, "10:00:02")
        
        self.assertEqual(turns[2].speaker, "CONSULTANT")
        self.assertEqual(turns[2].text, "Let me check that for you.")
        
        self.assertEqual(turns[3].speaker, "CLIENT")
        self.assertEqual(turns[3].text, "Thank you.")

    def test_coalesce_adjacent_same_speaker_segments(self):
        consultant = [
            TranscriptSegment(start_seconds=0.0, end_seconds=2.0, text="Hello.", speaker="CONSULTANT"),
            TranscriptSegment(start_seconds=2.5, end_seconds=4.0, text="How can I help you?", speaker="CONSULTANT"),
        ]
        client = []
        
        turns = merge_speaker_streams(consultant, client)
        self.assertEqual(len(turns), 1)
        self.assertEqual(turns[0].speaker, "CONSULTANT")
        self.assertEqual(turns[0].text, "Hello. How can I help you?")

    def test_empty_streams(self):
        turns = merge_speaker_streams([], [])
        self.assertEqual(turns, [])
        self.assertEqual(render_transcript_text(turns), "")

class TestTranscriptionPipeline(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.mic_path = os.path.join(self.test_dir, "test_mic.wav")
        self.loop_path = os.path.join(self.test_dir, "test_loop.wav")
        
        # Create dummy non-empty audio files
        with open(self.mic_path, "wb") as f:
            f.write(b"RIFF" + b"\x00"*2000)
        with open(self.loop_path, "wb") as f:
            f.write(b"RIFF" + b"\x00"*2000)
            
    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_pipeline_with_mock_provider(self):
        provider = MockTranscriptionProvider()
        pipeline = TranscriptionPipeline(provider=provider)
        
        call_time = datetime(2026, 10, 6, 14, 30, 0)
        out_dir = os.path.join(self.test_dir, "output")
        
        result = pipeline.process_session(
            consultant_audio_path=self.mic_path,
            client_audio_path=self.loop_path,
            call_start_time=call_time,
            output_dir=out_dir
        )
        
        self.assertEqual(result["status"], "success")
        self.assertTrue(result["total_dialogue_turns"] > 0)
        self.assertTrue(os.path.exists(os.path.join(out_dir, "transcript.txt")))
        self.assertTrue(os.path.exists(os.path.join(out_dir, "transcript.json")))
        
        # Verify speaker labeling in rendered output
        text = result["transcript_text"]
        self.assertIn("CONSULTANT:", text)
        self.assertIn("CLIENT:", text)

    def test_pipeline_handles_missing_stream_gracefully(self):
        provider = MockTranscriptionProvider()
        pipeline = TranscriptionPipeline(provider=provider)
        
        # Pass non-existent client file
        result = pipeline.process_session(
            consultant_audio_path=self.mic_path,
            client_audio_path=os.path.join(self.test_dir, "nonexistent.wav"),
            call_start_time=datetime.now()
        )
        
        # Should be partial_success, not crash
        self.assertEqual(result["status"], "partial_success")
        self.assertIn("client_error", result["errors"])
        self.assertTrue(result["consultant_segments_count"] > 0)

if __name__ == "__main__":
    unittest.main()
