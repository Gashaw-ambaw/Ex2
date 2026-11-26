"""Polls (F3): the lecturer starts and closes a poll, students answer once, and the results are counted.
While a poll is open only the number of answers is given out."""
import json
import sqlite3
from contextlib import closing


class PollService:
    """Anonymous polls (FR-10, FR-11, D11). anon_id is a random browser id, never a student."""

    def __init__(self, db, clock, settings):
        self._db = db
        self._clock = clock
        self._settings = settings

    def start(self, session_id, question, options, correct):
        """options are the form fields, blank ones included. correct is the field number (from 0) or None."""
        question = (question or "").strip()
        fields = [(option or "").strip() for option in options]
        kept = [i for i, text in enumerate(fields) if text]
        low, high = self._settings.poll_options_min, self._settings.poll_options_max
        if not question or not low <= len(kept) <= high or (correct is not None and correct not in kept):
            raise ValueError(f"Write a question and {low} to {high} options.")
        # Blank fields are dropped, so the correct mark moves with its text.
        correct_index = None if correct is None else kept.index(correct)
        with closing(self._db.connect()) as conn:
            # One transaction: close and insert happen together.
            conn.execute("BEGIN IMMEDIATE")
            now = self._clock.now_iso()
            # Every open poll, also one from an earlier day: only one open poll can exist.
            conn.execute("UPDATE polls SET status = 'closed', closed_at = ? WHERE status = 'open'", (now,))
            new_id = conn.execute(
                "INSERT INTO polls (session_id, question, options_json, correct_index, status, created_at) "
                "VALUES (?, ?, ?, ?, 'open', ?)",
                (session_id, question, json.dumps([fields[i] for i in kept]), correct_index, now),
            ).lastrowid
            conn.commit()
        return new_id

    def close(self, poll_id):
        with closing(self._db.connect()) as conn, conn:
            conn.execute(
                "UPDATE polls SET status = 'closed', closed_at = ? WHERE id = ? AND status = 'open'",
                (self._clock.now_iso(), poll_id),
            )

    @staticmethod
    def _poll(row):
        return {
            "id": row["id"],
            "question": row["question"],
            "options": json.loads(row["options_json"]),
            "correct": row["correct_index"],
            "open": row["status"] == "open",
        }

    @staticmethod
    def _latest(conn, session_id):
        return conn.execute(
            "SELECT * FROM polls WHERE session_id = ? ORDER BY id DESC LIMIT 1", (session_id,)
        ).fetchone()

    def active(self, session_id):
        """The latest poll of the session, open or closed, or None."""
        with closing(self._db.connect()) as conn:
            row = self._latest(conn, session_id)
        return self._poll(row) if row else None

    def answer(self, session_id, poll_id, anon_id, option):
        """Returns "ok", "already" or "not accepted" (closed, not the active poll, or no such option)."""
        with closing(self._db.connect()) as conn:
            # BEGIN IMMEDIATE: the poll cannot close between the check and the insert.
            conn.execute("BEGIN IMMEDIATE")
            row = self._latest(conn, session_id)
            if (row is None or row["id"] != poll_id or row["status"] != "open"
                    or not 0 <= option < len(json.loads(row["options_json"]))):
                return "not accepted"
            try:
                conn.execute(
                    "INSERT INTO poll_answers (poll_id, anon_id, option_index, created_at) VALUES (?, ?, ?, ?)",
                    (poll_id, anon_id, option, self._clock.now_iso()),
                )
            except sqlite3.IntegrityError:
                return "already"  # one answer per browser (the primary key)
            conn.commit()
        return "ok"

    def answer_of(self, poll_id, anon_id):
        """The option number this browser chose, or None."""
        with closing(self._db.connect()) as conn:
            row = conn.execute(
                "SELECT option_index FROM poll_answers WHERE poll_id = ? AND anon_id = ?", (poll_id, anon_id)
            ).fetchone()
        return None if row is None else row["option_index"]

    def results(self, poll_id):
        """One rule for every caller: an open poll gives only the number of answers."""
        with closing(self._db.connect()) as conn:
            row = conn.execute("SELECT * FROM polls WHERE id = ?", (poll_id,)).fetchone()
            if row is None:
                raise ValueError("Unknown poll")
            chosen = [r[0] for r in conn.execute(
                "SELECT option_index FROM poll_answers WHERE poll_id = ?", (poll_id,)
            )]
        if row["status"] == "open":
            return {"open": True, "answered": len(chosen)}
        options = json.loads(row["options_json"])
        votes = [chosen.count(i) for i in range(len(options))]
        results = {"open": False, "answered": len(chosen), "votes": votes}
        correct = row["correct_index"]
        if correct is not None:
            results.update(correct=correct, right=votes[correct], wrong=len(chosen) - votes[correct])
        return results
