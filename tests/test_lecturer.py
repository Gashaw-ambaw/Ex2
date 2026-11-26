"""Tests of LecturerAccess: the password and the lock after wrong attempts."""
from datetime import datetime, timedelta, timezone

import pytest

from app.lecturer import LecturerAccess

START = datetime(2026, 11, 24, 10, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def access(settings, clock):
    clock.set(START)
    return LecturerAccess(settings, clock)


def wrong_attempts(access, n):
    return [access.login("not-the-password") for _ in range(n)]


def test_right_password_is_ok(access):
    assert access.login("test-password") == "ok"


def test_wrong_password_is_wrong(access):
    assert access.login("nope") == "wrong"


# Bad input must not crash the login.
def test_empty_password_is_wrong(access):
    assert access.login("") == "wrong"
    assert access.login(None) == "wrong"


# D26: after 5 wrong attempts login is locked, for everyone.
def test_fifth_wrong_attempt_locks(access):
    assert wrong_attempts(access, 5) == ["wrong"] * 4 + ["locked"]


# While locked, even the right password is refused.
def test_right_password_is_refused_while_locked(access, clock):
    wrong_attempts(access, 5)
    clock.set(START + timedelta(seconds=299))
    assert access.login("test-password") == "locked"


# The lock ends after LOGIN_LOCKOUT_SEC (300 s).
def test_lock_ends_after_lockout_time(access, clock):
    wrong_attempts(access, 5)
    clock.set(START + timedelta(seconds=300))
    assert access.login("test-password") == "ok"


# After the lock ends the counter starts again from zero.
def test_counter_restarts_after_lock_ends(access, clock):
    wrong_attempts(access, 5)
    clock.set(START + timedelta(seconds=300))
    assert wrong_attempts(access, 4) == ["wrong"] * 4


# A right password clears earlier wrong attempts.
def test_success_resets_the_counter(access):
    wrong_attempts(access, 4)
    assert access.login("test-password") == "ok"
    assert wrong_attempts(access, 4) == ["wrong"] * 4


# The counter lives in memory: a new object starts with no attempts (EDD 6).
def test_counter_is_in_memory_only(access, settings, clock):
    wrong_attempts(access, 4)
    assert LecturerAccess(settings, clock).login("nope") == "wrong"
