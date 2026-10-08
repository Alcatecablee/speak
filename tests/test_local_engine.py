"""
Unit tests for Speak V2 Localhost Engine API.
"""

import json
import unittest
from fastapi.testclient import TestClient

from local_engine.server import app, session_manager


class TestLocalEngineAPI(unittest.TestCase):
    """Tests the Local Engine FastAPI endpoints."""

    def setUp(self):
        self.client = TestClient(app)

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
        # Verify SessionManager._update_stage records completed stages
        session_manager.state = "processing"
        session_manager.completed_stages = []
        session_manager._update_stage("stopping", "Finalizing audio capture", "Flushing buffers")
        self.assertEqual(session_manager.stage, "stopping")
        self.assertEqual(session_manager.stage_label, "Finalizing audio capture")

        session_manager._update_stage("transcribing_consultant", "Transcribing consultant audio", "Processing mic")
        self.assertEqual(session_manager.stage, "transcribing_consultant")
        self.assertIn("stopping", session_manager.completed_stages)

        session_manager._update_stage("transcribing_client", "Transcribing client audio", "Processing loopback")
        self.assertEqual(session_manager.stage, "transcribing_client")
        self.assertIn("transcribing_consultant", session_manager.completed_stages)

        session_manager._update_stage("merging_transcript", "Merging speaker transcript", "Merging turns")
        self.assertIn("transcribing_client", session_manager.completed_stages)

        session_manager._update_stage("analysing", "Analyzing conversation", "AI extraction")
        self.assertIn("merging_transcript", session_manager.completed_stages)

        session_manager._update_stage("preparing_review", "Preparing Salesforce draft", "Formatting draft")
        self.assertIn("analysing", session_manager.completed_stages)

        # Reset session_manager state
        session_manager.state = "idle"
        session_manager.stage = "none"
        session_manager.stage_label = "Idle"
        session_manager.completed_stages = []

    def test_demo_load_sample(self):
        response = self.client.post("/demo/load-sample")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ready")
        self.assertEqual(data["session_id"], "sample_real_call_demo")

    def test_get_transcript(self):
        # Load sample first
        self.client.post("/demo/load-sample")
        response = self.client.get("/transcript")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("merged_turns", data["data"])

    def test_get_analysis(self):
        self.client.post("/demo/load-sample")
        response = self.client.get("/analysis")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["data"]["resolution_status"], "FOLLOW_UP_REQUIRED")

    def test_get_review(self):
        self.client.post("/demo/load-sample")
        response = self.client.get("/review")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("salesforce_draft", data)
        self.assertEqual(data["salesforce_draft"]["action"], "DRAFT_UPDATE")

    def test_session_provenance_and_live_marker(self):
        # 1. Set active session with live session marker
        live_id = "live_session_8472"
        marker = "LIVE SESSION TEST 8472"
        session_manager.session_id = live_id
        session_manager.session_type = "live"
        session_manager.state = "ready"
        session_manager.stage = "ready"
        session_manager.stage_label = "Ready"

        # Write mock live session artifacts into output_dir
        out_dir = session_manager.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        transcript_data = {
            "session_id": live_id,
            "session_type": "live",
            "merged_turns": [
                {"speaker": "CONSULTANT", "text": f"Hello, {marker} starting."},
                {"speaker": "CLIENT", "text": "Confirmed, received marker."}
            ],
            "total_turns": 2
        }
        (out_dir / "transcript.json").write_text(json.dumps(transcript_data), encoding="utf-8")
        (out_dir / "transcript.txt").write_text(f"[CONSULTANT]: Hello, {marker} starting.\n[CLIENT]: Confirmed, received marker.\n", encoding="utf-8")
        (out_dir / "analysis.json").write_text(json.dumps({
            "session_id": live_id,
            "session_type": "live",
            "executive_summary": f"Live test run containing {marker}",
            "resolution_status": "RESOLVED"
        }), encoding="utf-8")
        (out_dir / "analysis_review.md").write_text(f"# Review for {marker}\n\nResolved successfully.", encoding="utf-8")
        (out_dir / "salesforce_draft_payload.json").write_text(json.dumps({
            "action": "CREATE_CASE",
            "subject": f"Live Call - {marker}",
            "description": f"Notes for {marker}"
        }), encoding="utf-8")

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

        # 3. Verify mismatched session_id returns 404
        bad_res = self.client.get("/transcript?session_id=mismatched_session_999")
        self.assertEqual(bad_res.status_code, 404)

        bad_a_res = self.client.get("/analysis?session_id=mismatched_session_999")
        self.assertEqual(bad_a_res.status_code, 404)

        bad_r_res = self.client.get("/review?session_id=mismatched_session_999")
        self.assertEqual(bad_r_res.status_code, 404)


if __name__ == "__main__":
    unittest.main()

