"""
Operational Reliability, Hardening, and Concurrency Tests (P0.1.1).
Tests:
  1. Windows atomic replace with retry on transient PermissionError / sharing violations.
  2. Cleanup of temporary files on persistent write failure.
  3. Single-instance OS process lock acquisition, mutual exclusion, and release.
  4. Automatic rediscovery and draining of backpressured sessions into worker queue.
  5. Manual retry endpoint POST /sessions/{id}/retry:
     - Re-enqueues interrupted and errored sessions.
     - Enforces status eligibility (rejects active/recording/processing sessions with 409).
     - Validates required input artifacts (rejects missing audio/transcript).
     - Prevents duplicate enqueueing via _active_jobs tracking.
  6. Demo fixture relocation and SHA-256 integrity verification.
"""

import hashlib
import json
from pathlib import Path
import queue
import tempfile
import time
import unittest
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from local_engine.server import app, get_session_manager, verify_auth_token
from local_engine.capture_manager import (
    SessionManager,
    _atomic_replace_with_retry,
    atomic_write_json,
    atomic_write_text,
    EXPECTED_BENCHMARK_SHA256,
)
from local_engine.lock import SingleInstanceLock


class TestOperationalReliability(unittest.TestCase):
    """Verifies all P0.1.1 operational hardening requirements."""

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

    # ---------------------------------------------------------------- Windows Atomic Replace
    def test_atomic_replace_retries_transient_permission_error(self):
        """_atomic_replace_with_retry retries on transient PermissionError and succeeds."""
        target = self.output_path / "test_target.txt"
        target.write_text("initial content", encoding="utf-8")

        tmp = self.output_path / "test_target_tmp.txt"
        tmp.write_text("updated content", encoding="utf-8")

        attempts = 0
        real_replace = _atomic_replace_with_retry.__globals__["os"].replace

        def mock_replace(src, dst):
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                # Simulate Windows file locking / antivirus sharing violation
                raise PermissionError("Access is denied (simulated Windows sharing violation)")
            return real_replace(src, dst)

        with patch("local_engine.capture_manager.os.replace", side_effect=mock_replace):
            _atomic_replace_with_retry(tmp, target, max_retries=5, initial_delay=0.01)

        self.assertEqual(attempts, 3)
        self.assertEqual(target.read_text(encoding="utf-8"), "updated content")
        self.assertFalse(tmp.exists())

    def test_atomic_replace_cleans_up_on_persistent_failure(self):
        """On persistent failure, tmp file is unlinked safely and original remains intact."""
        target = self.output_path / "target_stable.txt"
        target.write_text("original preserved", encoding="utf-8")

        tmp = self.output_path / "target_failed.tmp"
        tmp.write_text("failed update", encoding="utf-8")

        with patch("local_engine.capture_manager.os.replace", side_effect=PermissionError("Locked permanently")):
            with self.assertRaises(PermissionError):
                _atomic_replace_with_retry(tmp, target, max_retries=3, initial_delay=0.01)

        self.assertFalse(tmp.exists(), "Temporary file must be cleaned up on failure")
        self.assertEqual(target.read_text(encoding="utf-8"), "original preserved")

    # ---------------------------------------------------------------- Single Instance Lock
    def test_single_instance_lock_mutual_exclusion(self):
        """SingleInstanceLock grants access to the first caller and blocks secondary callers."""
        lock1 = SingleInstanceLock(lock_dir=self.output_path)
        lock2 = SingleInstanceLock(lock_dir=self.output_path)

        # Instance 1 acquires successfully
        self.assertTrue(lock1.acquire(), "First instance must acquire the lock")

        # Instance 2 is blocked from acquiring the same lock
        self.assertFalse(lock2.acquire(), "Secondary instance must be rejected while first holds lock")

        # Instance 1 releases
        lock1.release()

        # Instance 2 can now acquire
        self.assertTrue(lock2.acquire(), "Secondary instance acquires lock after primary releases")
        lock2.release()

    # ---------------------------------------------------------------- Backpressure Rediscovery
    def test_automatic_queue_rediscovery_of_backpressure(self):
        """_drain_backpressured_sessions drains disk-persisted backpressured jobs into queue."""
        session_id = self.mgr.generate_session_id(prefix="session")
        s_dir = self.output_path / session_id
        s_dir.mkdir(parents=True)

        (s_dir / "consultant_mic.wav").write_bytes(b"RIFFmockwav")
        (s_dir / "client_loopback.wav").write_bytes(b"RIFFmockwav")

        meta = {
            "session_id": session_id,
            "session_type": "live",
            "status": "queued_backpressure",
            "stage": "queued_backpressure",
            "created_at": "2026-10-14T10:00:00"
        }
        atomic_write_json(s_dir / "session_metadata.json", meta)

        # Before drain: queue is empty, job is backpressured
        self.assertEqual(self.mgr.processing_queue.qsize(), 0)

        # Drain
        self.mgr._drain_backpressured_sessions()

        # After drain: job is discovered and re-enqueued
        self.assertEqual(self.mgr.processing_queue.qsize(), 1)
        job = self.mgr.processing_queue.get_nowait()
        self.assertEqual(job["session_id"], session_id)
        self.assertIn(session_id, self.mgr._active_jobs)

        # Verify disk metadata transitioned to 'queued'
        updated_meta = self.mgr._read_metadata(s_dir)
        self.assertEqual(updated_meta["status"], "queued")
        self.mgr._active_jobs.discard(session_id)

    # ---------------------------------------------------------------- Manual Retry Endpoint
    def test_retry_session_interrupted(self):
        """POST /sessions/{id}/retry successfully re-enqueues an interrupted session."""
        session_id = self.mgr.generate_session_id(prefix="session")
        s_dir = self.output_path / session_id
        s_dir.mkdir(parents=True)

        (s_dir / "consultant_mic.wav").write_bytes(b"RIFFmockwav")
        (s_dir / "client_loopback.wav").write_bytes(b"RIFFmockwav")

        meta = {
            "session_id": session_id,
            "session_type": "live",
            "status": "interrupted",
            "stage": "interrupted",
            "error_message": "Process terminated"
        }
        atomic_write_json(s_dir / "session_metadata.json", meta)

        res = self.client.post(f"/sessions/{session_id}/retry")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "queued")
        self.assertEqual(data["session_id"], session_id)

        # Verify metadata was updated
        updated_meta = self.mgr._read_metadata(s_dir)
        self.assertEqual(updated_meta["status"], "queued")
        self.assertIsNone(updated_meta.get("error_message"))
        self.assertIn("retried_at", updated_meta)

    def test_retry_session_ineligible_status_rejected(self):
        """POST /sessions/{id}/retry rejects retrying an active or in-flight session with 409."""
        session_id = self.mgr.generate_session_id(prefix="session")
        s_dir = self.output_path / session_id
        s_dir.mkdir(parents=True)
        (s_dir / "consultant_mic.wav").write_bytes(b"RIFFmockwav")
        (s_dir / "client_loopback.wav").write_bytes(b"RIFFmockwav")

        meta = {
            "session_id": session_id,
            "session_type": "live",
            "status": "recording",
            "stage": "recording"
        }
        atomic_write_json(s_dir / "session_metadata.json", meta)

        res = self.client.post(f"/sessions/{session_id}/retry")
        self.assertEqual(res.status_code, 409)
        self.assertIn("recording", res.json()["detail"].lower())

    def test_retry_session_missing_artifacts_rejected(self):
        """POST /sessions/{id}/retry rejects session with no audio and no transcript with 404."""
        session_id = self.mgr.generate_session_id(prefix="session")
        s_dir = self.output_path / session_id
        s_dir.mkdir(parents=True)

        meta = {
            "session_id": session_id,
            "session_type": "live",
            "status": "error",
            "stage": "error"
        }
        atomic_write_json(s_dir / "session_metadata.json", meta)

        res = self.client.post(f"/sessions/{session_id}/retry")
        self.assertEqual(res.status_code, 404)
        self.assertIn("artifacts", res.json()["detail"].lower())

    def test_retry_session_duplicate_guard(self):
        """POST /sessions/{id}/retry prevents duplicate concurrent processing."""
        session_id = self.mgr.generate_session_id(prefix="session")
        s_dir = self.output_path / session_id
        s_dir.mkdir(parents=True)
        (s_dir / "consultant_mic.wav").write_bytes(b"RIFFmockwav")
        (s_dir / "client_loopback.wav").write_bytes(b"RIFFmockwav")

        meta = {"session_id": session_id, "status": "error"}
        atomic_write_json(s_dir / "session_metadata.json", meta)

        # Mark as currently active in jobs
        self.mgr._active_jobs.add(session_id)
        try:
            res = self.client.post(f"/sessions/{session_id}/retry")
            self.assertEqual(res.status_code, 409)
            self.assertIn("already", res.json()["detail"].lower())
        finally:
            self.mgr._active_jobs.discard(session_id)

    def test_retry_session_queued_rejected(self):
        """POST /sessions/{id}/retry rejects retrying an already queued session (idempotency)."""
        session_id = self.mgr.generate_session_id(prefix="session")
        s_dir = self.output_path / session_id
        s_dir.mkdir(parents=True)
        (s_dir / "consultant_mic.wav").write_bytes(b"RIFFmockwav")
        (s_dir / "client_loopback.wav").write_bytes(b"RIFFmockwav")

        meta = {"session_id": session_id, "status": "queued"}
        atomic_write_json(s_dir / "session_metadata.json", meta)

        res = self.client.post(f"/sessions/{session_id}/retry")
        self.assertEqual(res.status_code, 409)
        self.assertIn("status 'queued'", res.json()["detail"].lower())

    # ---------------------------------------------------------------- Fixture Integrity
    def test_benchmark_fixture_hash_and_immutability(self):
        """fixtures/demo_sample_transcript.json exists, matches SHA-256, and is never mutated."""
        fixture_path = Path("fixtures/demo_sample_transcript.json")
        self.assertTrue(fixture_path.exists(), "Benchmark fixture must exist in fixtures/")

        content = fixture_path.read_bytes()
        computed_hash = hashlib.sha256(content).hexdigest()
        self.assertEqual(
            computed_hash,
            EXPECTED_BENCHMARK_SHA256,
            f"Fixture SHA-256 hash mismatch! Expected {EXPECTED_BENCHMARK_SHA256}, got {computed_hash}"
        )

        # Verify load_demo_sample does not mutate the source fixture
        self.mgr.load_demo_sample()
        post_content = fixture_path.read_bytes()
        post_hash = hashlib.sha256(post_content).hexdigest()
        self.assertEqual(post_hash, EXPECTED_BENCHMARK_SHA256)

    def test_demo_sample_not_in_recordings_dir(self):
        """Confirm demo fixture is no longer stored in the active recordings output directory."""
        legacy_path = Path("recordings/demo_sample_transcript.json")
        self.assertFalse(legacy_path.exists(), "recordings/demo_sample_transcript.json must be removed")


if __name__ == "__main__":
    unittest.main()
