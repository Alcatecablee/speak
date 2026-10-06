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
        self.assertIn("has_transcript", data)

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
