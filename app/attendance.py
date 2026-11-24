import math
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime

# D31: shown when "Open attendance" is used on a session whose window was already open.
CLOSED_MESSAGE = "Attendance already closed for this session"


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
        # One session per date: if there is one already, it is returned and nothing is added.
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

    def count_marks(self, session_id):
        with closing(self._db.connect()) as conn:
            return conn.execute("SELECT COUNT(*) FROM marks WHERE session_id = ?", (session_id,)).fetchone()[0]
