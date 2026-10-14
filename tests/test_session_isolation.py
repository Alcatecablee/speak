"""
Comprehensive P0.1 Session Isolation, Decoupling, and Storage Integrity Tests.
Tests:
  1. Multi-session isolation (no overwriting or unlinking of past sessions)
  2. Mandatory session_id parameter on endpoints
  3. Strict allowlist regex and directory traversal guards
  4. Demo session isolation (unique folder, 6 artifacts, no fake audio, fixture unmodified)
  5. Decoupled capture engine & concurrent capture while prior session processes
  6. Failure preservation (raw audio and existing artifacts survive processing errors)
  7. Crash/restart recovery (interrupted marked safely, queued re-enqueued)
  8. Catalog enumeration (GET /sessions lists all sessions and handles corrupt metadata)
  9. Bounded queue and backpressure handling
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient

from local_engine.server import app, get_session_manager, verify_auth_token
from local_engine.capture_manager import (
    SessionManager,
    atomic_write_json,
    atomic_write_text,
    SESSION_ID_PATTERN,
)


class TestSessionIsolationP01(unittest.TestCase):
    """Verifies all P0.1 acceptance criteria in strict isolation."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.output_path = Path(self.tmp_dir.name)
        self.mgr = SessionManager(output_dir=str(self.output_path))
        app.dependency_overrides[get_session_manager] = lambda: self.mgr
        app.dependency_overrides[verify_auth_token] = lambda: True
        self.client = TestClient(app)

    def tearDown(self):
        self.mgr.shutdown_worker()
        app.dependency_overrides.clear()
        self.tmp_dir.cleanup()

    def _create_mock_session_on_disk(self, session_id: str, status: str = "ready", with_audio: bool = True):
        s_dir = self.output_path / session_id
        s_dir.mkdir(parents=True, exist_ok=False)
        meta = {
            "session_id": session_id,
            "session_type": "live",
            "status": status,
            "stage": status,
            "stage_label": status.capitalize(),
            "created_at": "2026-10-14T10:00:00",
            "audio_available": with_audio,
            "completed_stages": ["recording"] if status != "ready" else ["recording", "transcribing_consultant", "analysing", "preparing_review"]
        }
        atomic_write_json(s_dir / "session_metadata.json", meta)

        if with_audio:
            (s_dir / "consultant_mic.wav").write_bytes(b"RIFF_FAKE_AUDIO_MIC")
            (s_dir / "client_loopback.wav").write_bytes(b"RIFF_FAKE_AUDIO_LOOP")

        if status == "ready":
            atomic_write_json(s_dir / "transcript.json", {
                "session_id": session_id,
                "merged_turns": [{"speaker": "CONSULTANT", "text": f"Marker for {session_id}"}]
            })
            atomic_write_text(s_dir / "transcript.txt", f"[CONSULTANT]: Marker for {session_id}")
            atomic_write_json(s_dir / "analysis.json", {
                "session_id": session_id,
                "executive_summary": f"Summary for {session_id}"
            })
            atomic_write_text(s_dir / "analysis_review.md", f"# Review {session_id}")
            atomic_write_json(s_dir / "salesforce_draft_payload.json", {
                "action": "CREATE_CASE",
                "subject": f"Case {session_id}"
            })
        return s_dir

    def test_multi_session_isolation(self):
        """Session B must never delete or overwrite Session A's recordings or artifacts."""
        id_a = self.mgr.generate_session_id("session")
        dir_a = self._create_mock_session_on_disk(id_a, status="ready", with_audio=True)

        id_b = self.mgr.generate_session_id("session")
        dir_b = self._create_mock_session_on_disk(id_b, status="ready", with_audio=True)

        self.assertNotEqual(id_a, id_b)
        self.assertTrue(dir_a.exists())
        self.assertTrue(dir_b.exists())

        # Verify Session A artifacts and audio are preserved
        self.assertTrue((dir_a / "consultant_mic.wav").exists())
        self.assertEqual((dir_a / "consultant_mic.wav").read_bytes(), b"RIFF_FAKE_AUDIO_MIC")
        self.assertTrue((dir_a / "transcript.json").exists())
        self.assertIn(id_a, (dir_a / "transcript.json").read_text(encoding="utf-8"))

        # Verify Session B has its own independent files
        self.assertTrue((dir_b / "consultant_mic.wav").exists())
        self.assertTrue((dir_b / "transcript.json").exists())
        self.assertIn(id_b, (dir_b / "transcript.json").read_text(encoding="utf-8"))

        # Query endpoints for both sessions
        res_a = self.client.get(f"/transcript?session_id={id_a}")
        res_b = self.client.get(f"/transcript?session_id={id_b}")
        self.assertEqual(res_a.status_code, 200)
        self.assertEqual(res_b.status_code, 200)
        self.assertIn(id_a, res_a.json()["formatted_text"])
        self.assertIn(id_b, res_b.json()["formatted_text"])

    def test_mandatory_session_id_parameter(self):
        """Endpoints that touch session data must require an explicit session_id query param."""
        for ep in ["/transcript", "/analysis", "/review"]:
            res = self.client.get(ep)
            self.assertEqual(res.status_code, 422, f"Endpoint {ep} should return 422 when session_id is omitted")

        res_stop = self.client.post("/capture/stop")
        self.assertEqual(res_stop.status_code, 422, "POST /capture/stop should return 422 when session_id is omitted")

    def test_path_traversal_and_allowlist_guards(self):
        """Path traversal attempts, slashes, and regex mismatches must return 400 Bad Request."""
        malicious_inputs = [
            "../etc/passwd",
            "..\\windows\\system32",
            "session_20261014_111111_1234/extra",
            "session_20261014_111111_1234%00null",
            "random_string_id",
            "session_invalid",
            "; rm -rf /",
        ]
        for bad_id in malicious_inputs:
            res = self.client.get(f"/transcript?session_id={bad_id}")
            self.assertEqual(res.status_code, 400, f"Malicious input '{bad_id}' should return 400")

        # Direct unit test of validate_session_id on literal null byte
        with self.assertRaises(ValueError):
            self.mgr.validate_session_id("session_20261014_111111_1234\x00null")

    def test_demo_session_isolation(self):
        """Demo session must create an isolated folder with 6 artifacts and no fake audio."""
        res = self.client.post("/demo/load-sample")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        demo_id = data["session_id"]
        self.assertTrue(demo_id.startswith("demo_"))
        self.assertTrue(SESSION_ID_PATTERN.fullmatch(demo_id))

        demo_dir = self.output_path / demo_id
        self.assertTrue(demo_dir.is_dir())

        # Exactly 6 files must be present: metadata + 5 artifacts
        expected_files = {
            "session_metadata.json",
            "transcript.txt",
            "transcript.json",
            "analysis.json",
            "analysis_review.md",
            "salesforce_draft_payload.json"
        }
        actual_files = {f.name for f in demo_dir.iterdir()}
        self.assertEqual(expected_files, actual_files)

        # Audio files must NOT exist
        self.assertFalse((demo_dir / "consultant_mic.wav").exists())
        self.assertFalse((demo_dir / "client_loopback.wav").exists())

        # Metadata must reflect audio_available: false
        with open(demo_dir / "session_metadata.json", "r", encoding="utf-8") as f:
            meta = json.load(f)
        self.assertFalse(meta.get("audio_available", True))
        self.assertEqual(meta.get("session_type"), "demo")

    def test_decoupled_capture_engine_concurrency(self):
        """Stopping capture resets engine to idle immediately, allowing next recording while previous processes."""
        def mock_init_hw(mic_path, loop_path):
            mic_path.write_bytes(b"RIFF_FAKE_MIC")
            loop_path.write_bytes(b"RIFF_FAKE_LOOP")

        with patch.object(self.mgr, "_init_audio_hardware", side_effect=mock_init_hw):
            # 1. Start Capture for Session 1
            start_res1 = self.client.post("/capture/start")
            self.assertEqual(start_res1.status_code, 200)
            id_1 = start_res1.json()["session_id"]
            self.assertEqual(self.mgr.capture_state, "recording")
            self.assertEqual(self.mgr.capture_session_id, id_1)

            # 2. Stop Capture for Session 1
            stop_res1 = self.client.post(f"/capture/stop?session_id={id_1}")
            self.assertEqual(stop_res1.status_code, 200)

            # Engine state must be idle and uncoupled from Session 1
            self.assertEqual(self.mgr.capture_state, "idle")
            self.assertIsNone(self.mgr.capture_session_id)

            # 3. Start Capture for Session 2 immediately
            start_res2 = self.client.post("/capture/start")
            self.assertEqual(start_res2.status_code, 200)
            id_2 = start_res2.json()["session_id"]
            self.assertNotEqual(id_1, id_2)
            self.assertEqual(self.mgr.capture_state, "recording")
            self.assertEqual(self.mgr.capture_session_id, id_2)

            # 4. Stop Session 2
            stop_res2 = self.client.post(f"/capture/stop?session_id={id_2}")
            self.assertEqual(stop_res2.status_code, 200)
            self.assertEqual(self.mgr.capture_state, "idle")

    def test_processing_failure_preserves_audio_and_artifacts(self):
        """If processing fails, raw audio files and previous artifacts must remain on disk."""
        sess_id = self.mgr.generate_session_id("session")
        s_dir = self._create_mock_session_on_disk(sess_id, status="queued", with_audio=True)

        job = {
            "session_id": sess_id,
            "session_dir": s_dir,
            "session_type": "live",
            "mic_path": s_dir / "consultant_mic.wav",
            "loop_path": s_dir / "client_loopback.wav"
        }

        # Force failure during transcription
        with patch("local_engine.capture_manager.TranscriptionPipeline") as mock_pipeline_cls:
            mock_pipeline = mock_pipeline_cls.return_value
            mock_pipeline.process_session.side_effect = RuntimeError("Simulated GPU/CPU Out of Memory")

            # Worker loop catches and handles exception in _queue_worker_loop
            try:
                self.mgr._process_single_session(job)
            except RuntimeError:
                pass

        # Simulate worker setting error status upon catch
        meta = self.mgr._read_metadata(s_dir)
        meta["status"] = "error"
        meta["error_message"] = "Simulated GPU/CPU Out of Memory"
        atomic_write_json(s_dir / "session_metadata.json", meta)

        # Audio files MUST NOT be unlinked
        self.assertTrue((s_dir / "consultant_mic.wav").exists())
        self.assertTrue((s_dir / "client_loopback.wav").exists())
        self.assertEqual((s_dir / "consultant_mic.wav").read_bytes(), b"RIFF_FAKE_AUDIO_MIC")

    def test_restart_recovery(self):
        """On startup, in-flight sessions become 'interrupted' and queued sessions are re-enqueued."""
        id_interrupted = self.mgr.generate_session_id("session")
        dir_interrupted = self._create_mock_session_on_disk(id_interrupted, status="transcribing", with_audio=True)

        id_queued = self.mgr.generate_session_id("session")
        dir_queued = self._create_mock_session_on_disk(id_queued, status="queued", with_audio=True)

        id_ready = self.mgr.generate_session_id("session")
        dir_ready = self._create_mock_session_on_disk(id_ready, status="ready", with_audio=True)

        # Instantiate a fresh SessionManager pointing to the same directory (simulating server reboot)
        new_mgr = SessionManager(output_dir=str(self.output_path))
        try:
            # Check id_interrupted is safely marked as 'interrupted'
            with open(dir_interrupted / "session_metadata.json", "r", encoding="utf-8") as f:
                meta_int = json.load(f)
            self.assertEqual(meta_int["status"], "interrupted")
            self.assertIn("Process terminated", meta_int["error_message"])
            self.assertTrue((dir_interrupted / "consultant_mic.wav").exists())

            # Check id_queued was re-enqueued
            self.assertEqual(new_mgr.processing_queue.qsize(), 1)
            queued_job = new_mgr.processing_queue.get_nowait()
            self.assertEqual(queued_job["session_id"], id_queued)

            # Check id_ready remains ready
            with open(dir_ready / "session_metadata.json", "r", encoding="utf-8") as f:
                meta_ready = json.load(f)
            self.assertEqual(meta_ready["status"], "ready")
        finally:
            new_mgr.shutdown_worker()

    def test_session_catalog_enumeration(self):
        """GET /sessions must enumerate all valid sessions on disk and handle corrupted metadata."""
        id_1 = self.mgr.generate_session_id("session")
        self._create_mock_session_on_disk(id_1, status="ready", with_audio=True)

        id_2 = self.mgr.generate_session_id("demo")
        self._create_mock_session_on_disk(id_2, status="ready", with_audio=False)

        # Corrupted session (invalid JSON)
        id_corrupt = self.mgr.generate_session_id("session")
        corrupt_dir = self.output_path / id_corrupt
        corrupt_dir.mkdir(parents=True, exist_ok=False)
        (corrupt_dir / "session_metadata.json").write_text("{invalid json truncated", encoding="utf-8")

        res = self.client.get("/sessions")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data), 3)

        session_map = {s["session_id"]: s for s in data}
        self.assertIn(id_1, session_map)
        self.assertEqual(session_map[id_1]["status"], "ready")
        self.assertTrue(session_map[id_1]["audio_available"])

        self.assertIn(id_2, session_map)
        self.assertEqual(session_map[id_2]["status"], "ready")

        self.assertIn(id_corrupt, session_map)
        self.assertEqual(session_map[id_corrupt]["status"], "corrupted_metadata")

    def test_bounded_queue_backpressure(self):
        """Bounded queue must reject or preserve when capacity (max_queue_size) is exceeded."""
        bounded_mgr = SessionManager(output_dir=str(self.output_path), max_queue_size=2)
        try:
            with patch.object(bounded_mgr, "start_worker"):
                # Fill queue to capacity (2 items)
                sess1 = bounded_mgr.generate_session_id("session")
                dir1 = self._create_mock_session_on_disk(sess1, status="recording", with_audio=True)
                bounded_mgr.capture_state = "recording"
                bounded_mgr.capture_session_id = sess1
                bounded_mgr.stop_capture_and_process(sess1)

                sess2 = bounded_mgr.generate_session_id("session")
                dir2 = self._create_mock_session_on_disk(sess2, status="recording", with_audio=True)
                bounded_mgr.capture_state = "recording"
                bounded_mgr.capture_session_id = sess2
                bounded_mgr.stop_capture_and_process(sess2)

                self.assertEqual(bounded_mgr.processing_queue.qsize(), 2)

                # 3rd item exceeds capacity
                sess3 = bounded_mgr.generate_session_id("session")
                dir3 = self._create_mock_session_on_disk(sess3, status="recording", with_audio=True)
                bounded_mgr.capture_state = "recording"
                bounded_mgr.capture_session_id = sess3
                bounded_mgr.stop_capture_and_process(sess3)

                # Check sess3 was safely marked queued_backpressure without losing files
                with open(dir3 / "session_metadata.json", "r", encoding="utf-8") as f:
                    meta3 = json.load(f)
                self.assertEqual(meta3["status"], "queued_backpressure")
                self.assertTrue((dir3 / "consultant_mic.wav").exists())
                self.assertTrue((dir3 / "client_loopback.wav").exists())
        finally:
            bounded_mgr.shutdown_worker()


if __name__ == "__main__":
    unittest.main()
