"""
Single-instance OS-level file lock for Speak Local Engine.
Prevents concurrent engine processes from conflicting on the same storage directory.
Supports Windows (msvcrt.locking) and POSIX (fcntl.flock).
"""

import logging
import os
from pathlib import Path
import sys
from typing import Optional

logger = logging.getLogger("speak.lock")


class SingleInstanceLock:
    """
    Acquires an exclusive OS-level non-blocking file lock on .engine.lock.
    Guarantees that only one engine process manages the recordings directory at a time.
    """

    def __init__(self, lock_dir: Path):
        self.lock_dir = Path(lock_dir).resolve()
        self.lock_path = self.lock_dir / ".engine.lock"
        self._fp = None
        self._is_locked = False

    def acquire(self) -> bool:
        """
        Attempts to acquire the lock non-blocking.
        Returns True if acquired, False if already held by another process.
        """
        try:
            self.lock_dir.mkdir(parents=True, exist_ok=True)
            self._fp = open(self.lock_path, "a+b")

            if sys.platform == "win32":
                import msvcrt
                self._fp.seek(0)
                try:
                    msvcrt.locking(self._fp.fileno(), msvcrt.LK_NBLCK, 1)
                except (OSError, PermissionError):
                    self._cleanup_handle()
                    return False
            else:
                import fcntl
                try:
                    fcntl.flock(self._fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except (BlockingIOError, OSError):
                    self._cleanup_handle()
                    return False

            # Lock acquired: write PID for diagnostic inspection
            try:
                self._fp.seek(0)
                self._fp.truncate(0)
                self._fp.write(f"{os.getpid()}\n".encode("utf-8"))
                self._fp.flush()
            except Exception:
                pass

            self._is_locked = True
            logger.info(f"Acquired single-instance lock on {self.lock_path} (PID: {os.getpid()})")
            return True

        except Exception as e:
            logger.warning(f"Failed to acquire single-instance lock: {e}")
            self._cleanup_handle()
            return False

    def release(self) -> None:
        """Releases the lock and removes the lock file if owned."""
        if not self._is_locked or self._fp is None:
            return

        try:
            if sys.platform == "win32":
                import msvcrt
                try:
                    self._fp.seek(0)
                    msvcrt.locking(self._fp.fileno(), msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
            else:
                import fcntl
                try:
                    fcntl.flock(self._fp.fileno(), fcntl.LOCK_UN)
                except OSError:
                    pass
        finally:
            self._cleanup_handle()
            self._is_locked = False
            try:
                if self.lock_path.exists():
                    self.lock_path.unlink()
            except OSError:
                pass
            logger.info("Released single-instance lock.")

    def _cleanup_handle(self) -> None:
        if self._fp:
            try:
                self._fp.close()
            except OSError:
                pass
            self._fp = None
