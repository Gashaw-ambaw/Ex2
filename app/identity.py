from contextlib import closing
from dataclasses import dataclass, field

from authlib.integrations.base_client import OAuthError


@dataclass
class RegisterResult:
    """entry is None when the email is not on the roster (nothing was written)."""

    entry: object = None
    events: list = field(default_factory=list)


class StudentIdentity:
    """Who is this browser? Google sign-in, then a device link to one roster entry (FR-03, D8, D16)."""

    def __init__(self, db, clock, roster, google):
        self._db = db
        self._clock = clock
        self._roster = roster
        # google is the Authlib client (oauth.google). Tests pass a fake.
        self._google = google

    async def start_sign_in(self, request, redirect_uri):
        return await self._google.authorize_redirect(request, redirect_uri)

    async def verify_google(self, request):
        """Returns the verified email in lower case. Nothing is written (D24)."""
        try:
            token = await self._google.authorize_access_token(request)
        except OAuthError:
            # The student cancelled, or Google refused.
            raise ValueError("Google sign-in was cancelled or failed.") from None
        info = (token or {}).get("userinfo") or {}
        email = (info.get("email") or "").strip().lower()
        if not email or info.get("email_verified") is not True:
            raise ValueError("Your Google email is not verified.")
        return email

    def confirm_registration(self, device_id, email):
        # Only active roster entries can register (D8).
        entry = self._roster.find_by_email(email)
        if entry is None or not entry["active"]:
            return RegisterResult()
        events = []
        with closing(self._db.connect()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            device = conn.execute("SELECT * FROM devices WHERE id = ?", (device_id,)).fetchone()
            if device is None:
                # A second device for the same student is flagged (D16); the first one is not.
                others = conn.execute(
                    "SELECT COUNT(*) FROM devices WHERE roster_id = ?", (entry["id"],)
                ).fetchone()[0]
                conn.execute(
                    "INSERT INTO devices (id, roster_id, created_at) VALUES (?, ?, ?)",
                    (device_id, entry["id"], self._clock.now_iso()),
                )
                if others:
                    events.append("new_device")
            elif device["roster_id"] != entry["id"]:
                # This browser was linked to another student: it is linked to the new one and flagged.
                conn.execute("UPDATE devices SET roster_id = ? WHERE id = ?", (entry["id"], device_id))
                events.append("relinked")
            conn.commit()
        return RegisterResult(entry, events)

    def device_owner(self, device_id):
        # Marking checks only this link (EDD 3).
        if not device_id:
            return None
        with closing(self._db.connect()) as conn:
            return conn.execute(
                "SELECT r.* FROM devices d JOIN roster_entries r ON r.id = d.roster_id WHERE d.id = ?",
                (device_id,),
            ).fetchone()
