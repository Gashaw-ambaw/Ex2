"""Lecturer access: one password, logout, and a short lock after too many wrong attempts."""
import hmac
import threading
from datetime import timedelta

from fastapi import HTTPException


class LecturerAccess:
    """One lecturer password, a signed session, and a lockout after wrong attempts (FR-17, D26)."""

    def __init__(self, settings, clock):
        self._password = settings.lecturer_password.encode()
        self._limit = settings.login_attempt_limit
        self._lockout = timedelta(seconds=settings.login_lockout_sec)
        self._clock = clock
        # The counter is in memory only. It resets when the server restarts (D26).
        self._wrong = 0
        self._locked_until = None
        # Requests run in several threads, so the counter is changed under a lock.
        self._lock = threading.Lock()

    def login(self, password):
        # Returns "ok", "wrong" or "locked". The lock is for everyone.
        with self._lock:
            now = self._clock.now()
            if self._locked_until is not None:
                if now < self._locked_until:
                    return "locked"
                self._locked_until = None
                self._wrong = 0
            # compare_digest takes the same time for any input, so timing leaks nothing.
            given = password.encode() if isinstance(password, str) else b""
            if hmac.compare_digest(given, self._password):
                self._wrong = 0
                return "ok"
            self._wrong += 1
            if self._wrong >= self._limit:
                self._locked_until = now + self._lockout
                self._wrong = 0
                return "locked"
            return "wrong"

    def logout(self, request):
        request.session.clear()

    def require_lecturer(self, request):
        # Used as a FastAPI dependency: without the session flag, go to the login page.
        if not request.session.get("lecturer"):
            raise HTTPException(status_code=303, headers={"Location": "/login"})
