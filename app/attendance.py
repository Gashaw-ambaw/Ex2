import math
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime

from app.clock import ISRAEL

# D31: shown when "Open attendance" is used on a session whose window was already open.
CLOSED_MESSAGE = "Attendance already closed for this session"


@dataclass(frozen=True)
class ScanTicket:
    """Proof of a scan: kept in the signed session cookie. scanned_at is in whole seconds (UTC)."""

    session_id: int
    scanned_at: int


FLAG_KINDS = ("new_device", "relinked", "device_reuse", "location")

# UC-03 5b: the same text for a scan and a tap on a closed window.
ATTENDANCE_CLOSED = "Attendance is closed; ask the lecturer."


@dataclass(frozen=True)
class MarkResult:
    """outcome: "marked", "already" or "blocked". time: HH:MM in Israel time (the mark, or the earlier one)."""

    outcome: str
    time: str = ""


def distance_m(lat1, lon1, lat2, lon2):
    """Haversine distance in metres (EDD 5)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(a))


@dataclass(frozen=True)
class WindowState:
    open: bool
    seconds_left: int
    marks: int
    flags: int


def parse_location(text):
    """Read "lat, lon" (decimal, as copied from Google Maps). Raises ValueError if it is not that."""
    parts = (text or "").split(",")
    if len(parts) != 2:
        raise ValueError('Write the location as "lat, lon", for example 32.0853, 34.7818.')
    try:
        lat, lon = float(parts[0]), float(parts[1])
    except ValueError:
        raise ValueError('Write the location as "lat, lon", for example 32.0853, 34.7818.') from None
    if not (math.isfinite(lat) and math.isfinite(lon)):
        raise ValueError('Write the location as "lat, lon", for example 32.0853, 34.7818.')
    return lat, lon


class AttendanceService:
    """Class sessions, the class location and the attendance window (FR-02, D19, D28).
    Marking rules are added in step 6."""

    def __init__(self, db, clock, settings, qr_tokens):
        self._db = db
        self._clock = clock
        self._settings = settings
        self._qr = qr_tokens

    # ---- Sessions ----

    def session_for_today(self):
        with closing(self._db.connect()) as conn:
            return conn.execute(
                "SELECT * FROM class_sessions WHERE date = ? ORDER BY id DESC LIMIT 1",
                (self._clock.today().isoformat(),),
            ).fetchone()

    def start_class(self):
        # Start class reuses today's latest session; new_session() adds another one (D31).
        # BEGIN IMMEDIATE blocks a second request until this one has finished.
        with closing(self._db.connect()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            today = self._clock.today().isoformat()
            row = conn.execute(
                "SELECT * FROM class_sessions WHERE date = ? ORDER BY id DESC LIMIT 1", (today,)
            ).fetchone()
            if row is None:
                conn.execute("INSERT INTO class_sessions (date) VALUES (?)", (today,))
                row = conn.execute("SELECT * FROM class_sessions WHERE id = last_insert_rowid()").fetchone()
            conn.commit()
            return row

    def new_session(self, name=None):
        """UC-01 1b (D31): a new session for today, for example after a closed window.
        The old session and its marks stay. Refused while today's window is open."""
        name = (name or "").strip() or None
        with closing(self._db.connect()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            today = self._clock.today().isoformat()
            latest = conn.execute(
                "SELECT * FROM class_sessions WHERE date = ? ORDER BY id DESC LIMIT 1", (today,)
            ).fetchone()
            if latest is not None and self._is_open(latest, self._clock.now()):
                raise ValueError("Close attendance first.")
            conn.execute("INSERT INTO class_sessions (date, name) VALUES (?, ?)", (today, name))
            row = conn.execute("SELECT * FROM class_sessions WHERE id = last_insert_rowid()").fetchone()
            conn.commit()
            return row

    def _session(self, conn, session_id):
        row = conn.execute("SELECT * FROM class_sessions WHERE id = ?", (session_id,)).fetchone()
        if row is None:
            raise ValueError("Unknown session")
        return row

    # ---- The class location (D28) ----

    def class_location(self):
        with closing(self._db.connect()) as conn:
            row = conn.execute("SELECT lat, lon FROM class_location WHERE id = 1").fetchone()
        return (row["lat"], row["lon"]) if row else None

    def set_class_location(self, lat, lon):
        # Written so that nan also fails (every comparison with nan is False).
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("Latitude must be between -90 and 90, and longitude between -180 and 180.")
        with closing(self._db.connect()) as conn, conn:
            conn.execute(
                "INSERT INTO class_location (id, lat, lon, updated_at) VALUES (1, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET lat = excluded.lat, lon = excluded.lon, updated_at = excluded.updated_at",
                (lat, lon, self._clock.now_iso()),
            )

    # ---- The attendance window ----

    @staticmethod
    def _is_open(row, now):
        # Window closed = window_closed_at set or now >= window_ends_at. Expiry writes nothing.
        if row["window_opened_at"] is None or row["window_closed_at"] is not None:
            return False
        return now < datetime.fromisoformat(row["window_ends_at"])

    def open_window(self, session_id):
        with closing(self._db.connect()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self._session(conn, session_id)
            now = self._clock.now()
            if self._is_open(row, now):
                return  # a double tap changes nothing
            if row["window_opened_at"] is not None:
                raise ValueError(CLOSED_MESSAGE)  # D31
            ends = now.timestamp() + self._settings.att_window_sec
            ends_iso = datetime.fromtimestamp(ends, now.tzinfo).isoformat(timespec="seconds")
            conn.execute(
                "UPDATE class_sessions SET window_opened_at = ?, window_ends_at = ? WHERE id = ?",
                (self._clock.now_iso(), ends_iso, session_id),
            )
            conn.commit()

    def close_window(self, session_id):
        with closing(self._db.connect()) as conn, conn:
            row = self._session(conn, session_id)
            if self._is_open(row, self._clock.now()):
                conn.execute(
                    "UPDATE class_sessions SET window_closed_at = ? WHERE id = ?",
                    (self._clock.now_iso(), session_id),
                )

    def window_state(self, session_id):
        # Read only: this runs on every poll of the lecturer page.
        with closing(self._db.connect()) as conn:
            row = self._session(conn, session_id)
            marks = conn.execute("SELECT COUNT(*) FROM marks WHERE session_id = ?", (session_id,)).fetchone()[0]
            flags = conn.execute("SELECT COUNT(*) FROM flags WHERE session_id = ?", (session_id,)).fetchone()[0]
        now = self._clock.now()
        is_open = self._is_open(row, now)
        left = 0
        if is_open:
            left = math.ceil((datetime.fromisoformat(row["window_ends_at"]) - now).total_seconds())
        return WindowState(is_open, left, marks, flags)

    def current_qr(self, session_id):
        """The address inside the QR now, or None when the window is not open."""
        if not self.window_state(session_id).open:
            return None
        window = self._qr.window()
        token = self._qr.make(session_id, window)
        return f"{self._settings.base_url}/scan?s={session_id}&w={window}&t={token}"

    def check_scan(self, s, w, t):
        """UC-03 steps 1-2: is this a live QR of an open window? Values come from the address, so they are text."""
        if self.session_for_today() is None:
            raise ValueError("Class has not started.")
        try:
            session_id, window = int(s), int(w)
        except (TypeError, ValueError):
            raise ValueError("Scan again.") from None
        with closing(self._db.connect()) as conn:
            row = conn.execute("SELECT * FROM class_sessions WHERE id = ?", (session_id,)).fetchone()
        if row is None:
            raise ValueError("Scan again.")
        # The closed check comes first: after Close, a live scan must hear "closed", not "scan again".
        if not self._is_open(row, self._clock.now()):
            raise ValueError(ATTENDANCE_CLOSED)
        if not self._qr.verify(session_id, window, t):
            raise ValueError("Scan again.")
        return ScanTicket(session_id, int(self._clock.now().timestamp()))

    def ticket_is_fresh(self, scanned_at):
        # A mark or a registration is accepted for SUBMIT_SEC seconds after the scan (EDD 5).
        return int(self._clock.now().timestamp()) - scanned_at <= self._settings.submit_sec

    def add_flags(self, session_id, roster_id, device_id, kinds):
        # Warnings for the lecturer only (D16). They never block anyone.
        if any(kind not in FLAG_KINDS for kind in kinds):
            raise ValueError("Unknown flag kind.")
        with closing(self._db.connect()) as conn, conn:
            self._insert_flags(conn, session_id, roster_id, device_id, kinds)

    def _insert_flags(self, conn, session_id, roster_id, device_id, kinds):
        for kind in kinds:
            conn.execute(
                "INSERT INTO flags (session_id, roster_id, device_id, kind, created_at) VALUES (?, ?, ?, ?, ?)",
                (session_id, roster_id, device_id, kind, self._clock.now_iso()),
            )

    def mark(self, device_id, ticket, location):
        """UC-03 steps 5-6. location is (lat, lon), or None when the browser did not send one.
        Raises ValueError with the text for the student; otherwise returns a MarkResult."""
        if not self.ticket_is_fresh(ticket.scanned_at):
            raise ValueError("Scan the QR again.")
        with closing(self._db.connect()) as conn:
            conn.execute("BEGIN IMMEDIATE")  # one writer at a time: two taps cannot both insert
            session = self._session(conn, ticket.session_id)
            if not self._is_open(session, self._clock.now()):
                raise ValueError(ATTENDANCE_CLOSED)
            # Marking checks only the device link (EDD 3).
            student = conn.execute(
                "SELECT r.id FROM devices d JOIN roster_entries r ON r.id = d.roster_id WHERE d.id = ?",
                (device_id or "",),
            ).fetchone()
            if student is None:
                raise ValueError("Scan the QR in class first.")
            roster_id = student["id"]
            earlier = conn.execute(
                "SELECT marked_at FROM marks WHERE session_id = ? AND roster_id = ?", (ticket.session_id, roster_id)
            ).fetchone()
            if earlier is not None:
                return MarkResult("already", self._israel_hhmm(earlier["marked_at"]))
            used = conn.execute(
                "SELECT 1 FROM marks WHERE session_id = ? AND device_id = ?", (ticket.session_id, device_id)
            ).fetchone()
            if used is not None:
                self._insert_flags(conn, ticket.session_id, roster_id, device_id, ["device_reuse"])
                conn.commit()
                return MarkResult("blocked")
            hall = conn.execute("SELECT lat, lon FROM class_location WHERE id = 1").fetchone()
            location_ok = None
            if hall is not None:
                location_ok = int(
                    location is not None
                    and distance_m(*location, hall["lat"], hall["lon"]) <= self._settings.loc_radius_m
                )
            conn.execute(
                "INSERT INTO marks (session_id, roster_id, device_id, marked_at, source, location_ok) "
                "VALUES (?, ?, ?, ?, 'self', ?)",
                (ticket.session_id, roster_id, device_id, self._clock.now_iso(), location_ok),
            )
            if location_ok == 0:
                self._insert_flags(conn, ticket.session_id, roster_id, device_id, ["location"])
            conn.commit()
            return MarkResult("marked", self._israel_hhmm(self._clock.now_iso()))

    @staticmethod
    def _israel_hhmm(iso):
        return datetime.fromisoformat(iso).astimezone(ISRAEL).strftime("%H:%M")

    def count_marks(self, session_id):
        with closing(self._db.connect()) as conn:
            return conn.execute("SELECT COUNT(*) FROM marks WHERE session_id = ?", (session_id,)).fetchone()[0]
