"""
Unit tests for Speak V2 Localhost Engine API with strict test isolation.
"""

import json
import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

from local_engine.server import app, get_session_manager, verify_auth_token
from local_engine.capture_manager import SessionManager, atomic_write_json, atomic_write_text


class TestLocalEngineAPI(unittest.TestCase):
    """Tests the Local Engine FastAPI endpoints with isolated storage."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.test_mgr = SessionManager(output_dir=self.tmp_dir.name)
        app.dependency_overrides[get_session_manager] = lambda: self.test_mgr
        app.dependency_overrides[verify_auth_token] = lambda: True
        self.client = TestClient(app)

    def tearDown(self):
        self.test_mgr.shutdown_worker()
        app.dependency_overrides.clear()
        self.tmp_dir.cleanup()

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertTrue(data["loopback_only"])

    def test_status_endpoint(self):
        response = self.client.get("/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)
        self.assertIn("stage", data)
        self.assertIn("stage_label", data)
        self.assertIn("message", data)
        self.assertIn("elapsed_seconds", data)
        self.assertIn("completed_stages", data)
        self.assertIn("has_transcript", data)

    def test_stage_tracking_state_machine(self):
        # Create a test session in temporary directory
        session_id = self.test_mgr.generate_session_id(prefix="session")
        session_dir = Path(self.test_mgr.output_dir) / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        meta = {
            "session_id": session_id,
            "session_type": "live",
            "status": "processing",
            "stage": "transcribing_consultant",
            "stage_label": "Transcribing audio",
            "completed_stages": []
        }
        atomic_write_json(session_dir / "session_metadata.json", meta)

        status_data = self.test_mgr.get_status(session_id=session_id)
        self.assertEqual(status_data["stage"], "transcribing_consultant")
        self.assertEqual(status_data["stage_label"], "Transcribing audio")

        # Progress through stages
        meta["stage"] = "transcribing_client"
        meta["completed_stages"].append("transcribing_consultant")
        atomic_write_json(session_dir / "session_metadata.json", meta)

        status_data = self.test_mgr.get_status(session_id=session_id)
        self.assertEqual(status_data["stage"], "transcribing_client")
        self.assertIn("transcribing_consultant", status_data["completed_stages"])

        meta["stage"] = "merging_transcript"
        meta["completed_stages"].append("transcribing_client")
        atomic_write_json(session_dir / "session_metadata.json", meta)

        status_data = self.test_mgr.get_status(session_id=session_id)
        self.assertIn("transcribing_client", status_data["completed_stages"])

        meta["stage"] = "analysing"
        meta["stage_label"] = "Analyzing conversation"
        meta["completed_stages"].append("merging_transcript")
        atomic_write_json(session_dir / "session_metadata.json", meta)

        status_data = self.test_mgr.get_status(session_id=session_id)
        self.assertEqual(status_data["stage"], "analysing")
        self.assertIn("merging_transcript", status_data["completed_stages"])

        meta["status"] = "ready"
        meta["stage"] = "ready"
        meta["stage_label"] = "Processing complete"
        meta["completed_stages"].extend(["analysing", "preparing_review"])
        atomic_write_json(session_dir / "session_metadata.json", meta)

        status_data = self.test_mgr.get_status(session_id=session_id)
        self.assertEqual(status_data["status"], "ready")
        self.assertIn("preparing_review", status_data["completed_stages"])

    def test_demo_load_sample(self):
        response = self.client.post("/demo/load-sample")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ready")
        self.assertTrue(data["session_id"].startswith("demo_"))

    def test_get_transcript(self):
        load_res = self.client.post("/demo/load-sample")
        demo_id = load_res.json()["session_id"]

        # Missing session_id must return 422
        res_missing = self.client.get("/transcript")
        self.assertEqual(res_missing.status_code, 422)

        # Explicit session_id returns 200
        response = self.client.get(f"/transcript?session_id={demo_id}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("merged_turns", data["data"])

    def test_get_analysis(self):
        load_res = self.client.post("/demo/load-sample")
        demo_id = load_res.json()["session_id"]

        # Missing session_id must return 422
        res_missing = self.client.get("/analysis")
        self.assertEqual(res_missing.status_code, 422)

        response = self.client.get(f"/analysis?session_id={demo_id}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["data"]["resolution_status"], "FOLLOW_UP_REQUIRED")

    def test_get_review(self):
        load_res = self.client.post("/demo/load-sample")
        demo_id = load_res.json()["session_id"]

        # Missing session_id must return 422
        res_missing = self.client.get("/review")
        self.assertEqual(res_missing.status_code, 422)

        response = self.client.get(f"/review?session_id={demo_id}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("salesforce_draft", data)
        self.assertEqual(data["salesforce_draft"]["action"], "DRAFT_UPDATE")

    def test_session_provenance_and_live_marker(self):
        live_id = self.test_mgr.generate_session_id(prefix="session")
        marker = "LIVE SESSION TEST 8472"

        out_dir = Path(self.test_mgr.output_dir) / live_id
        out_dir.mkdir(parents=True, exist_ok=True)

        meta = {
            "session_id": live_id,
            "session_type": "live",
            "status": "ready",
            "stage": "ready",
            "stage_label": "Ready",
            "created_at": "2026-10-14T10:00:00",
            "completed_stages": ["recording", "transcribing_consultant", "transcribing_client", "merging_transcript", "analysing", "preparing_review"]
        }
        atomic_write_json(out_dir / "session_metadata.json", meta)

        transcript_data = {
            "session_id": live_id,
            "session_type": "live",
            "merged_turns": [
                {"speaker": "CONSULTANT", "text": f"Hello, {marker} starting."},
                {"speaker": "CLIENT", "text": "Confirmed, received marker."}
            ],
            "total_turns": 2
        }
        atomic_write_json(out_dir / "transcript.json", transcript_data)
        atomic_write_text(out_dir / "transcript.txt", f"[CONSULTANT]: Hello, {marker} starting.\n[CLIENT]: Confirmed, received marker.\n")
        atomic_write_json(out_dir / "analysis.json", {
            "session_id": live_id,
            "session_type": "live",
            "executive_summary": f"Live test run containing {marker}",
            "resolution_status": "RESOLVED"
        })
        atomic_write_text(out_dir / "analysis_review.md", f"# Review for {marker}\n\nResolved successfully.")
        atomic_write_json(out_dir / "salesforce_draft_payload.json", {
            "action": "CREATE_CASE",
            "subject": f"Live Call - {marker}",
            "description": f"Notes for {marker}"
        })

        # 2. Verify endpoints return correct live session data with matching session_id
        t_res = self.client.get(f"/transcript?session_id={live_id}")
        self.assertEqual(t_res.status_code, 200)
        t_json = t_res.json()
        self.assertEqual(t_json["session_id"], live_id)
        self.assertEqual(t_json["session_type"], "live")
        self.assertIn(marker, t_json["formatted_text"])

        a_res = self.client.get(f"/analysis?session_id={live_id}")
        self.assertEqual(a_res.status_code, 200)
        a_json = a_res.json()
        self.assertEqual(a_json["session_id"], live_id)
        self.assertEqual(a_json["session_type"], "live")
        self.assertIn(marker, a_json["data"]["executive_summary"])

        r_res = self.client.get(f"/review?session_id={live_id}")
        self.assertEqual(r_res.status_code, 200)
        r_json = r_res.json()
        self.assertEqual(r_json["session_id"], live_id)
        self.assertEqual(r_json["session_type"], "live")
        self.assertIn(marker, r_json["markdown"])
        self.assertIn(marker, r_json["salesforce_draft"]["subject"])

        # 3. Verify non-existent valid session_id returns 404
        non_existent_id = self.test_mgr.generate_session_id(prefix="session")
        bad_res = self.client.get(f"/transcript?session_id={non_existent_id}")
        self.assertEqual(bad_res.status_code, 404)

        bad_a_res = self.client.get(f"/analysis?session_id={non_existent_id}")
        self.assertEqual(bad_a_res.status_code, 404)

        bad_r_res = self.client.get(f"/review?session_id={non_existent_id}")
        self.assertEqual(bad_r_res.status_code, 404)

        # 4. Verify invalid session_id format returns 400
        invalid_format_res = self.client.get("/transcript?session_id=bad_id_123")
        self.assertEqual(invalid_format_res.status_code, 400)


if __name__ == "__main__":
    unittest.main()
