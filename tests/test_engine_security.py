"""
Unit and integration tests for Speak Local Engine Security (P0.2 Hardened).
Tests:
  1. Unauthenticated requests to protected endpoints return 401 Unauthorized.
  2. Public health check (/health) returns 200 without authentication.
  3. Valid X-Speak-Engine-Auth header authenticates successfully.
  4. Valid Authorization: Bearer <token> authenticates successfully.
  5. Invalid token returns 401 Unauthorized.
  6. Disallowed Origin returns 403 Forbidden.
  7. Allowed Origins (dev mode vs prod mode via SPEAK_ENV).
  8. Pairing endpoint (/auth/pair) exchanges 6-digit code for token in POST body.
  9. Single-use pairing code is consumed immediately upon successful pairing.
  10. Pairing rate-limiting triggers timed cooldown (HTTP 429) after 5 failed attempts.
  11. Cooldown recovery allows valid pairing once cooldown expires.
  12. Expired pairing code past TTL (300s) is rejected with HTTP 403.
  13. Safe code regeneration clears lockout and generates new valid code.
  14. Constant-time token verification via hmac.compare_digest.
  15. Log secret redaction filter removes tokens and pairing codes from log output.
  16. Route-by-route audit: every sensitive operational route enforces authentication.
"""

import logging
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from local_engine.auth import AuthManager, AuthSecretRedactionFilter
from local_engine.server import app, get_auth_manager, get_session_manager
from local_engine.capture_manager import SessionManager


class TestEngineSecurity(unittest.TestCase):
    """Verifies all P0.2 security and authentication controls."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.mgr = SessionManager(output_dir=self.tmp_dir.name)
        # Use short cooldown in tests for fast testing
        self.auth_mgr = AuthManager(
            allowed_origins={"http://localhost:5173", "http://127.0.0.1:5173"},
            is_dev=True,
            cooldown_seconds=1.0,
            pairing_ttl_seconds=300.0
        )

        app.dependency_overrides[get_session_manager] = lambda: self.mgr
        app.dependency_overrides[get_auth_manager] = lambda: self.auth_mgr
        # Clear any bypass override
        app.dependency_overrides.pop("verify_auth_token", None)
        self.client = TestClient(app)

    def tearDown(self):
        self.mgr.shutdown_worker()
        app.dependency_overrides.clear()
        self.tmp_dir.cleanup()

    def test_health_endpoint_is_unauthenticated(self):
        """Health check endpoint must be publicly reachable on loopback without auth."""
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "ok")
        self.assertTrue(data["loopback_only"])

    def test_protected_endpoints_require_authentication(self):
        """All operational endpoints must reject unauthenticated requests with 401."""
        endpoints = [
            ("GET", "/status"),
            ("GET", "/sessions"),
            ("POST", "/capture/start"),
            ("POST", "/capture/stop?session_id=session_20261014_111111_0123456789abcdef0123456789abcdef"),
            ("GET", "/transcript?session_id=session_20261014_111111_0123456789abcdef0123456789abcdef"),
            ("GET", "/analysis?session_id=session_20261014_111111_0123456789abcdef0123456789abcdef"),
            ("GET", "/review?session_id=session_20261014_111111_0123456789abcdef0123456789abcdef"),
            ("POST", "/demo/load-sample"),
            ("POST", "/sessions/session_20261014_111111_0123456789abcdef0123456789abcdef/retry"),
        ]
        for method, path in endpoints:
            with self.subTest(method=method, path=path):
                if method == "GET":
                    res = self.client.get(path)
                else:
                    res = self.client.post(path)
                self.assertEqual(
                    res.status_code, 401,
                    f"Expected 401 for unauthenticated {method} {path}, got {res.status_code}"
                )

    def test_invalid_token_rejected(self):
        """Requests with an invalid auth token must be rejected with 401."""
        res = self.client.get("/status", headers={"X-Speak-Engine-Auth": "bogus_token_12345"})
        self.assertEqual(res.status_code, 401)
        self.assertIn("Unauthorized", res.json()["detail"])

    def test_valid_custom_header_token_accepted(self):
        """Requests with valid X-Speak-Engine-Auth header must succeed."""
        valid_token = self.auth_mgr.session_token
        res = self.client.get("/status", headers={"X-Speak-Engine-Auth": valid_token})
        self.assertEqual(res.status_code, 200)

    def test_valid_bearer_token_accepted(self):
        """Requests with valid Authorization: Bearer <token> must succeed."""
        valid_token = self.auth_mgr.session_token
        res = self.client.get("/status", headers={"Authorization": f"Bearer {valid_token}"})
        self.assertEqual(res.status_code, 200)

    def test_origin_allowlist_enforcement_dev_mode(self):
        """In dev mode, explicitly allowed dev origins are accepted; external origins are rejected."""
        valid_token = self.auth_mgr.session_token

        # Permitted origin
        res_ok = self.client.get(
            "/status",
            headers={"X-Speak-Engine-Auth": valid_token, "Origin": "http://localhost:5173"}
        )
        self.assertEqual(res_ok.status_code, 200)

        # Disallowed malicious origin
        res_blocked = self.client.get(
            "/status",
            headers={"X-Speak-Engine-Auth": valid_token, "Origin": "https://malicious-site.example.com"}
        )
        self.assertEqual(res_blocked.status_code, 403)
        self.assertIn("Forbidden", res_blocked.json()["detail"])

    def test_origin_allowlist_production_mode(self):
        """In production mode (is_dev=False), localhost origins are disallowed."""
        prod_auth_mgr = AuthManager(is_dev=False)
        self.assertNotIn("http://localhost:5173", prod_auth_mgr.allowed_origins)
        self.assertIn("https://speak-plum.vercel.app", prod_auth_mgr.allowed_origins)
        self.assertFalse(prod_auth_mgr.is_origin_allowed("http://localhost:5173"))
        self.assertTrue(prod_auth_mgr.is_origin_allowed("https://speak-plum.vercel.app"))

    def test_pairing_code_bootstrap_flow(self):
        """Valid 6-digit pairing code in POST body returns the session token."""
        code = self.auth_mgr.pairing_code
        res = self.client.post(
            "/auth/pair",
            json={"pairing_code": code},
            headers={"Origin": "http://localhost:5173"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "paired")
        self.assertEqual(data["auth_token"], self.auth_mgr.session_token)

    def test_single_use_pairing_code_consumed(self):
        """Pairing code is single-use and invalidated immediately after first successful pair."""
        code = self.auth_mgr.pairing_code
        # First use succeeds
        res1 = self.client.post("/auth/pair", json={"pairing_code": code})
        self.assertEqual(res1.status_code, 200)

        # Second use with the same code fails (code was consumed)
        res2 = self.client.post("/auth/pair", json={"pairing_code": code})
        self.assertEqual(res2.status_code, 403)

    def test_pairing_rate_limiting_and_timed_cooldown(self):
        """Pairing endpoint enforces 5 failed attempts then locks for timed cooldown (HTTP 429)."""
        # Attempt 1-4: Invalid codes return 403
        for i in range(4):
            res = self.client.post("/auth/pair", json={"pairing_code": f"00000{i}"})
            self.assertEqual(res.status_code, 403)

        # Attempt 5: 5th failure triggers cooldown lockout
        res_fifth = self.client.post("/auth/pair", json={"pairing_code": "000005"})
        self.assertEqual(res_fifth.status_code, 429)
        self.assertIn("cooldown", res_fifth.json()["detail"].lower())

        # Attempt 6: Locked in cooldown
        real_code = self.auth_mgr.pairing_code
        res_locked = self.client.post("/auth/pair", json={"pairing_code": real_code})
        self.assertEqual(res_locked.status_code, 429)

        # After cooldown duration expires, requests are accepted again
        time.sleep(1.1)
        self.assertFalse(self.auth_mgr.is_in_cooldown())
        res_after = self.client.post("/auth/pair", json={"pairing_code": real_code})
        self.assertEqual(res_after.status_code, 200)

    def test_expired_pairing_code_rejected(self):
        """Pairing code older than TTL is rejected with 403."""
        # Artificially expire the pairing code
        self.auth_mgr.pairing_code_created_at = time.time() - 305
        real_code = self.auth_mgr.pairing_code
        res = self.client.post("/auth/pair", json={"pairing_code": real_code})
        self.assertEqual(res.status_code, 403)
        self.assertIn("expired", res.json()["detail"].lower())

    def test_safe_code_regeneration(self):
        """regenerate_pairing_code clears lockout and creates a fresh valid code."""
        # Put into cooldown
        self.auth_mgr._lockout_until = time.time() + 100
        self.assertTrue(self.auth_mgr.is_in_cooldown())

        # Regenerate
        new_code = self.auth_mgr.regenerate_pairing_code()
        self.assertFalse(self.auth_mgr.is_in_cooldown())
        self.assertEqual(len(new_code), 6)

        # New code pairs successfully
        res = self.client.post("/auth/pair", json={"pairing_code": new_code})
        self.assertEqual(res.status_code, 200)

    def test_pairing_origin_enforcement(self):
        """Disallowed Origin cannot call the pairing endpoint."""
        code = self.auth_mgr.pairing_code
        res = self.client.post(
            "/auth/pair",
            json={"pairing_code": code},
            headers={"Origin": "https://attacker.evil"}
        )
        self.assertEqual(res.status_code, 403)

    def test_constant_time_token_verification(self):
        """AuthManager.verify_token correctly matches tokens in constant time."""
        token = self.auth_mgr.session_token
        self.assertTrue(self.auth_mgr.verify_token(token))
        self.assertFalse(self.auth_mgr.verify_token("invalid_token"))
        self.assertFalse(self.auth_mgr.verify_token(""))
        self.assertFalse(self.auth_mgr.verify_token(None))

    def test_log_secret_redaction_filter(self):
        """AuthSecretRedactionFilter scrubs token and pairing code from log messages."""
        token = self.auth_mgr.session_token
        code = self.auth_mgr.pairing_code

        filter_instance = AuthSecretRedactionFilter(self.auth_mgr)

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=10,
            msg=f"Client authenticated with token {token} and code {code}",
            args=(),
            exc_info=None
        )

        filter_instance.filter(record)
        self.assertNotIn(token, record.getMessage())
        if code:
            self.assertNotIn(code, record.getMessage())
        self.assertIn("[REDACTED_AUTH_TOKEN]", record.getMessage())


if __name__ == "__main__":
    unittest.main()
