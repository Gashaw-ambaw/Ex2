"""Anonymous comments (F2): saves a comment and lists comments for the student and the lecturer.
No name or email is stored."""
from contextlib import closing
from datetime import datetime, timedelta

from app.clock import ISRAEL


class CommentService:
    """Anonymous comments (FR-08, FR-09, D10). anon_id is a random browser id, never a student."""

    def __init__(self, db, clock, settings):
        self._db = db
        self._clock = clock
        self._settings = settings

    def send(self, session_id, anon_id, text):
        # A browser form sends a line break as two characters; it counts as one.
        text = (text or "").replace("\r\n", "\n").strip()
        limit = self._settings.comment_max_chars
        if not 1 <= len(text) <= limit:
            raise ValueError(f"Write 1 to {limit} characters.")
        with closing(self._db.connect()) as conn:
            # BEGIN IMMEDIATE: a double tap cannot pass the time check twice.
            conn.execute("BEGIN IMMEDIATE")
            last = conn.execute("SELECT MAX(created_at) FROM comments WHERE anon_id = ?", (anon_id,)).fetchone()[0]
            wait = timedelta(seconds=self._settings.comment_min_interval_sec)
            if last is not None and self._clock.now() - datetime.fromisoformat(last) < wait:
                raise ValueError("Wait a moment.")
            conn.execute(
                "INSERT INTO comments (session_id, anon_id, text, created_at) VALUES (?, ?, ?, ?)",
                (session_id, anon_id, text, self._clock.now_iso()),
            )
            conn.commit()

    def own(self, anon_id, session_id):
        """This browser's comments in one session, newest first."""
        return self._list("session_id = ? AND anon_id = ?", (session_id, anon_id))

    def list_for_lecturer(self, session_id):
        """All comments of one session, newest first."""
        return self._list("session_id = ?", (session_id,))

    def _list(self, where, values):
        # "where" is one of the two fixed texts above; the values are always passed separately.
        with closing(self._db.connect()) as conn:
            found = conn.execute(
                f"SELECT text, created_at FROM comments WHERE {where} ORDER BY id DESC", values
            ).fetchall()
        return [
            {"time": datetime.fromisoformat(row["created_at"]).astimezone(ISRAEL).strftime("%H:%M"),
             "text": row["text"]}
            for row in found
        ]
