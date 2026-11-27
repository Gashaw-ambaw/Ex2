"""Head count (F1, UC-04): counts the people in a class photo, compares with the marks and stores the numbers.
The photo is only held in memory (D21)."""
import logging
from contextlib import closing

import cv2
import numpy as np

BAD_PHOTO = "The photo must be an image of at most {} MB."
FAILED = "Counting failed. No count was stored."


def count_gap(marks, count, tolerance_pct):
    """(gap, alert). Alert when marks are more than the count plus the tolerance. Whole numbers only."""
    return marks - count, marks * 100 > count * (100 + tolerance_pct)


class HeadCountService:
    def __init__(self, db, clock, settings, attendance, counter):
        self._db = db
        self._clock = clock
        self._settings = settings
        self._attendance = attendance
        self._counter = counter

    def count_photo(self, session_id, data):
        """data: the uploaded bytes. A new photo replaces the session's earlier count."""
        image = self._decode(data)
        try:
            count = int(self._counter.count(image))
        except Exception:
            logging.getLogger(__name__).exception("Head count failed")
            raise ValueError(FAILED) from None
        marks = self._attendance.count_marks(session_id)
        gap, alert = count_gap(marks, count, self._settings.gap_tolerance_pct)
        with closing(self._db.connect()) as conn, conn:
            conn.execute(
                "INSERT OR REPLACE INTO head_counts (session_id, count, source, marks_at_count, gap, alert, created_at) "
                "VALUES (?, ?, 'auto', ?, ?, ?, ?)",
                (session_id, count, marks, gap, int(alert), self._clock.now_iso()),
            )
        return {"count": count, "marks": marks, "gap": gap, "alert": alert}

    def _decode(self, data):
        limit = self._settings.photo_max_mb
        image = None
        if 0 < len(data) <= limit * 1024 * 1024:
            try:
                image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
            except cv2.error:  # for example a picture with too many pixels
                image = None
        if image is None:
            raise ValueError(BAD_PHOTO.format(limit))
        return image

    def result(self, session_id):
        """The stored count of the session, or None."""
        with closing(self._db.connect()) as conn:
            row = conn.execute("SELECT * FROM head_counts WHERE session_id = ?", (session_id,)).fetchone()
        if row is None:
            return None
        return {"count": row["count"], "marks": row["marks_at_count"], "gap": row["gap"], "alert": bool(row["alert"])}
