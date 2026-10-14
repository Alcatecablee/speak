"""
Security and Authentication Manager for Speak Local Engine (P0.2 Hardened).
Provides:
  - Ephemeral 256-bit cryptographically secure session auth token.
  - Short-lived, single-use 6-digit pairing code with bounded attempts,
    timed cooldown (60s), and safe regeneration.
  - Strict separation of Development vs Production origins via SPEAK_ENV.
  - Constant-time token verification using hmac.compare_digest.
  - Log secret redaction filter preventing credential exposure in logs.
"""

import hmac
import logging
import os
import secrets
import sys
import threading
import time
from typing import Optional, Set

logger = logging.getLogger("speak.auth")

DEFAULT_DEV_ORIGINS = {
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
}

DEFAULT_PROD_ORIGINS = {
    "https://speak-plum.vercel.app",
}


class AuthManager:
    """Manages ephemeral engine credentials, pairing flow, and origin verification."""

    def __init__(
        self,
        allowed_origins: Optional[Set[str]] = None,
        is_dev: Optional[bool] = None,
        pairing_ttl_seconds: float = 300.0,
        cooldown_seconds: float = 60.0
    ):
        self._lock = threading.RLock()
        self.session_token = secrets.token_urlsafe(32)
        self.pairing_code: Optional[str] = f"{secrets.randbelow(900000) + 100000}"
        self.pairing_code_created_at = time.time()
        self.pairing_ttl_seconds = pairing_ttl_seconds

        self._failed_pair_attempts = 0
        self._max_failed_pair_attempts = 5
        self.cooldown_seconds = cooldown_seconds
        self._lockout_until = 0.0

        # Determine environment mode: default to SPEAK_ENV or development if not set
        if is_dev is not None:
            self.is_dev = is_dev
        else:
            env_mode = os.environ.get("SPEAK_ENV", "development").lower()
            self.is_dev = (env_mode != "production")

        # In production mode: allow ONLY production origins
        # In development mode: allow development loopback origins + production
        if self.is_dev:
            self.allowed_origins = set(DEFAULT_DEV_ORIGINS) | set(DEFAULT_PROD_ORIGINS)
        else:
            self.allowed_origins = set(DEFAULT_PROD_ORIGINS)

        if allowed_origins:
            self.allowed_origins.update(allowed_origins)

        # Allow environment override for deployed origins (e.g. Vercel preview URLs)
        env_origins = os.environ.get("SPEAK_ALLOWED_ORIGINS")
        if env_origins:
            self.allowed_origins.update([o.strip() for o in env_origins.split(",") if o.strip()])

    def is_origin_allowed(self, origin: Optional[str]) -> bool:
        """
        Validates the Origin header against the explicit allowlist.
        If Origin header is missing (e.g. native local tool or non-browser client),
        it is permitted only if accompanied by valid session token authentication.
        """
        if not origin:
            return True
        norm = origin.rstrip("/")
        return norm in self.allowed_origins

    def verify_token(self, provided_token: Optional[str]) -> bool:
        """Validates the auth token using constant-time string comparison."""
        if not provided_token or not isinstance(provided_token, str):
            return False
        return hmac.compare_digest(provided_token, self.session_token)

    def is_in_cooldown(self) -> bool:
        """Returns True if the pairing endpoint is currently locked in cooldown."""
        with self._lock:
            return time.time() < self._lockout_until

    def get_remaining_cooldown(self) -> int:
        """Returns remaining cooldown seconds, or 0 if not locked."""
        with self._lock:
            now = time.time()
            if now < self._lockout_until:
                return max(1, int(self._lockout_until - now))
            return 0

    def is_code_expired(self) -> bool:
        """Returns True if the pairing code has expired past its TTL."""
        with self._lock:
            if not self.pairing_code:
                return True
            return (time.time() - self.pairing_code_created_at) > self.pairing_ttl_seconds

    def pair_with_code(self, candidate_code: str) -> Optional[str]:
        """
        Validates 6-digit pairing code with rate-limiting, TTL, and timed cooldown.
        Single-use: invalidates the pairing code immediately on success.
        Returns the session token on success, None on failure.
        """
        with self._lock:
            now = time.time()
            if now < self._lockout_until:
                remaining = int(self._lockout_until - now)
                logger.warning(f"Pairing attempt rejected: locked in cooldown ({remaining}s remaining).")
                return None

            if not self.pairing_code or (now - self.pairing_code_created_at) > self.pairing_ttl_seconds:
                logger.warning("Pairing attempt rejected: pairing code expired or not set.")
                return None

            clean_candidate = candidate_code.strip().replace("-", "")
            if hmac.compare_digest(clean_candidate, self.pairing_code):
                self._failed_pair_attempts = 0
                # Invalidate pairing code immediately after successful single use
                self.pairing_code = None
                logger.info("Browser successfully paired. Single-use pairing code consumed.")
                return self.session_token

            self._failed_pair_attempts += 1
            logger.warning(
                f"Invalid pairing attempt ({self._failed_pair_attempts}/{self._max_failed_pair_attempts})"
            )
            if self._failed_pair_attempts >= self._max_failed_pair_attempts:
                self._lockout_until = now + self.cooldown_seconds
                self._failed_pair_attempts = 0
                logger.warning(
                    f"Pairing locked for {self.cooldown_seconds}s cooldown due to excessive failed attempts."
                )
            return None

    def regenerate_pairing_code(self) -> str:
        """
        Generates a new short-lived, single-use 6-digit pairing code.
        Resets attempt counter and clears cooldown.
        """
        with self._lock:
            self.pairing_code = f"{secrets.randbelow(900000) + 100000}"
            self.pairing_code_created_at = time.time()
            self._failed_pair_attempts = 0
            self._lockout_until = 0.0
            return self.pairing_code

    def reset_credentials(self) -> None:
        """Rotates both session token and pairing code."""
        with self._lock:
            self.session_token = secrets.token_urlsafe(32)
            self.regenerate_pairing_code()


class AuthSecretRedactionFilter(logging.Filter):
    """Logging filter that scrubs auth tokens and pairing codes from all application log output."""

    def __init__(self, auth_manager: AuthManager):
        super().__init__()
        self.auth_manager = auth_manager

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
            token = self.auth_manager.session_token
            code = self.auth_manager.pairing_code

            redacted = False
            if token and token in msg:
                msg = msg.replace(token, "[REDACTED_AUTH_TOKEN]")
                redacted = True
            if code and code in msg:
                msg = msg.replace(code, "[REDACTED_PAIRING_CODE]")
                redacted = True

            if redacted:
                record.msg = msg
                record.args = ()
        except Exception:
            pass
        return True
