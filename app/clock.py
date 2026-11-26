"""The current time: stored in UTC, shown in Israel time. Tests can set a fixed time."""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

ISRAEL = ZoneInfo("Asia/Jerusalem")


class Clock:
    """Times are stored in UTC and shown in Israel time. Tests set the time."""

    def __init__(self):
        # None means "use the real time". A test can set a fixed time.
        self._fixed = None

    def set(self, moment):
        # A time with no timezone is ambiguous, so it is refused.
        if moment.tzinfo is None:
            raise ValueError("Clock.set needs a timezone-aware datetime")
        self._fixed = moment.astimezone(timezone.utc)

    def now(self):
        return self._fixed or datetime.now(timezone.utc)

    def now_iso(self):
        # Text form for the database, for example 2026-11-24T12:00:00+00:00.
        return self.now().isoformat(timespec="seconds")

    def israel_now(self):
        # For display only. ZoneInfo handles summer and winter time by itself.
        return self.now().astimezone(ISRAEL)

    def today(self) -> date:
        # A session date is the Israel date.
        return self.israel_now().date()
