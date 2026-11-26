"""Tests of StudentIdentity (F1): the device link, the flags and the Google sign-in result."""
import asyncio
from contextlib import closing

import pytest
from authlib.integrations.base_client import OAuthError

from app.identity import StudentIdentity
from app.roster import RosterService


class FakeGoogle:
    """Stands in for Google. No network."""

    def __init__(self, userinfo=None, error=None):
        self.userinfo = userinfo
        self.error = error

    async def authorize_redirect(self, request, redirect_uri):
        return ("redirect", redirect_uri)

    async def authorize_access_token(self, request):
        if self.error:
            raise OAuthError(self.error)
        return {"userinfo": self.userinfo}


@pytest.fixture
def roster(db, clock):
    service = RosterService(db, clock)
    service.save([
        {"first_name": "Dana", "last_name": "Levi", "email": "dana@example.com"},
        {"first_name": "Ron", "last_name": "Cohen", "email": "ron@example.com"},
    ])
    return service


@pytest.fixture
def identity(db, clock, roster):
    return StudentIdentity(db, clock, roster, FakeGoogle())


def devices(db):
    with closing(db.connect()) as conn:
        return {r["id"]: r["roster_id"] for r in conn.execute("SELECT * FROM devices").fetchall()}


def dana(roster):
    return roster.find_by_email("dana@example.com")["id"]


def ron(roster):
    return roster.find_by_email("ron@example.com")["id"]


# ---- confirm_registration ----

def test_first_device_is_linked_without_a_flag(identity, roster, db):
    result = identity.confirm_registration("dev-1", "dana@example.com")
    assert result.entry["first_name"] == "Dana"
    assert result.events == []
    assert devices(db) == {"dev-1": dana(roster)}


def test_email_is_matched_in_lower_case(identity, db):
    result = identity.confirm_registration("dev-1", "  DANA@Example.COM ")
    assert result.entry is not None
    assert "dev-1" in devices(db)


# TC-17: an email that is not on the roster writes nothing.
def test_email_not_on_the_roster_writes_nothing(identity, db):
    result = identity.confirm_registration("dev-1", "stranger@example.com")
    assert result.entry is None and result.events == []
    assert devices(db) == {}


def test_inactive_entry_cannot_register(identity, roster, db):
    # A new roster file without Ron makes him inactive.
    roster.save([{"first_name": "Dana", "last_name": "Levi", "email": "dana@example.com"}])
    result = identity.confirm_registration("dev-1", "ron@example.com")
    assert result.entry is None
    assert devices(db) == {}


# TC-18: a browser linked to student A registers as B: it is linked to B; flag relinked.
def test_browser_of_another_student_is_relinked(identity, roster, db):
    identity.confirm_registration("dev-1", "dana@example.com")
    result = identity.confirm_registration("dev-1", "ron@example.com")
    assert result.events == ["relinked"]
    assert devices(db) == {"dev-1": ron(roster)}


# TC-19: a second device for the same student is added; flag new_device.
def test_second_device_of_the_same_student_is_flagged(identity, roster, db):
    identity.confirm_registration("dev-1", "dana@example.com")
    result = identity.confirm_registration("dev-2", "dana@example.com")
    assert result.events == ["new_device"]
    assert devices(db) == {"dev-1": dana(roster), "dev-2": dana(roster)}


def test_same_device_same_student_again_changes_nothing(identity, roster, db):
    identity.confirm_registration("dev-1", "dana@example.com")
    result = identity.confirm_registration("dev-1", "dana@example.com")
    assert result.events == []
    assert devices(db) == {"dev-1": dana(roster)}


def test_a_device_of_another_student_does_not_count_as_new_device(identity):
    identity.confirm_registration("dev-1", "dana@example.com")
    result = identity.confirm_registration("dev-2", "ron@example.com")
    assert result.events == []


# ---- device_owner ----

def test_device_owner(identity):
    identity.confirm_registration("dev-1", "dana@example.com")
    assert identity.device_owner("dev-1")["first_name"] == "Dana"
    assert identity.device_owner("unknown") is None
    assert identity.device_owner(None) is None
    assert identity.device_owner("") is None


def test_device_owner_follows_the_relink(identity):
    identity.confirm_registration("dev-1", "dana@example.com")
    identity.confirm_registration("dev-1", "ron@example.com")
    assert identity.device_owner("dev-1")["first_name"] == "Ron"


# ---- Google ----

def make(db, clock, roster, google):
    return StudentIdentity(db, clock, roster, google)


def test_verify_google_returns_a_lower_case_email(db, clock, roster):
    google = FakeGoogle({"email": "Dana@Example.com", "email_verified": True})
    assert asyncio.run(make(db, clock, roster, google).verify_google(None)) == "dana@example.com"


@pytest.mark.parametrize("userinfo", [
    {"email": "dana@example.com", "email_verified": False},
    {"email": "dana@example.com"},
    {"email_verified": True},
    {"email": "", "email_verified": True},
    None,
])
def test_verify_google_refuses_an_unverified_or_missing_email(db, clock, roster, userinfo):
    with pytest.raises(ValueError):
        asyncio.run(make(db, clock, roster, FakeGoogle(userinfo)).verify_google(None))


# TC-16: the student cancels at Google.
def test_verify_google_cancelled(db, clock, roster):
    google = FakeGoogle(error="access_denied")
    with pytest.raises(ValueError, match="cancelled"):
        asyncio.run(make(db, clock, roster, google).verify_google(None))


def test_start_sign_in_uses_the_redirect_address(db, clock, roster):
    identity = make(db, clock, roster, FakeGoogle())
    assert asyncio.run(identity.start_sign_in(None, "https://x.test/auth/callback")) == (
        "redirect", "https://x.test/auth/callback")
