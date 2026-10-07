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


if __name__ == "__main__":
    unittest.main()
