"""Tests of the photo head count (F1): the gap rule, the service with a fake counter, and the real model."""
from contextlib import closing
from datetime import datetime, timezone

import cv2
import numpy as np
import pytest

from app.attendance import AttendanceService
from app.headcount import HeadCountService, count_gap
from app.people_counter import PeopleCounter
from app.qr_tokens import QrTokens
from app.roster import RosterService

NOON = datetime(2026, 11, 28, 12, 0, 0, tzinfo=timezone.utc)
PNG = cv2.imencode(".png", np.zeros((40, 60, 3), np.uint8))[1].tobytes()
BAD_PHOTO = "The photo must be an image of at most 10 MB."


class FakeCounter:
    def __init__(self, number=0, error=None):
        self.number = number
        self.error = error
        self.calls = 0

    def count(self, image):
        self.calls += 1
        assert image.shape == (40, 60, 3)
        if self.error:
            raise self.error
        return self.number


@pytest.fixture
def attendance(db, clock, settings):
    clock.set(NOON)
    return AttendanceService(db, clock, settings, QrTokens(settings.secret_key, settings.qr_rotate_sec, clock))


def make_class(db, clock, attendance, marks):
    """Today's session with this many marks of synthetic students."""
    roster = RosterService(db, clock)
    roster.save([{"first_name": "Test", "last_name": str(i), "email": f"s{i}@example.com"} for i in range(marks)])
    session = attendance.start_class()["id"]
    for entry in roster.list_active():
        attendance.add_manual(session, entry["id"])
    return session


def service(db, clock, settings, attendance, counter):
    return HeadCountService(db, clock, settings, attendance, counter)


def rows(db):
    with closing(db.connect()) as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM head_counts")]


# TC-28: alert when marks > count x 1.05.
@pytest.mark.parametrize("count, gap, alert", [(97, 7, True), (101, 3, False), (102, 2, False)])
def test_gap_rule_tc28(count, gap, alert):
    assert count_gap(104, count, 5) == (gap, alert)


def test_gap_rule_second_example_tc28():
    # 104 / 97 alerts and the exact border does not: 105 marks for 100 people is 5%, not more.
    assert count_gap(105, 100, 5) == (5, False)
    assert count_gap(106, 100, 5) == (6, True)


def test_gap_rule_nobody_counted():
    assert count_gap(1, 0, 5) == (1, True)
    assert count_gap(0, 0, 5) == (0, False)


# TC-31: more people than marks is never an alert.
def test_count_above_marks_tc31():
    assert count_gap(90, 100, 5) == (-10, False)


# TC-27 (service part): the numbers are stored.
def test_count_is_stored_tc27(db, clock, settings, attendance):
    session = make_class(db, clock, attendance, 104)
    result = service(db, clock, settings, attendance, FakeCounter(97)).count_photo(session, PNG)
    assert result == {"count": 97, "marks": 104, "gap": 7, "alert": True}
    [row] = rows(db)
    assert (row["session_id"], row["count"], row["source"], row["marks_at_count"], row["gap"], row["alert"]) == (
        session, 97, "auto", 104, 7, 1)


def test_result_before_any_photo(db, clock, settings, attendance):
    session = make_class(db, clock, attendance, 1)
    assert service(db, clock, settings, attendance, FakeCounter()).result(session) is None


# TC-29: not an image, empty, or over PHOTO_MAX_MB: an error, nothing counted or stored.
@pytest.mark.parametrize("data", [b"not an image", b"", PNG + b"0" * (10 * 1024 * 1024)],
                         ids=["text", "empty", "too large"])
def test_bad_photo_tc29(db, clock, settings, attendance, data):
    session = make_class(db, clock, attendance, 3)
    counter = FakeCounter(2)
    with pytest.raises(ValueError, match=BAD_PHOTO):
        service(db, clock, settings, attendance, counter).count_photo(session, data)
    assert counter.calls == 0 and rows(db) == []


# TC-30: the counter fails: an error, no count and no alert.
def test_counter_fails_tc30(db, clock, settings, attendance):
    session = make_class(db, clock, attendance, 3)
    heads = service(db, clock, settings, attendance, FakeCounter(error=RuntimeError("model")))
    with pytest.raises(ValueError, match="Counting failed. No count was stored."):
        heads.count_photo(session, PNG)
    assert rows(db) == [] and heads.result(session) is None


# TC-67: a second photo replaces the count.
def test_second_photo_replaces_tc67(db, clock, settings, attendance):
    session = make_class(db, clock, attendance, 10)
    counter = FakeCounter(2)
    heads = service(db, clock, settings, attendance, counter)
    heads.count_photo(session, PNG)
    counter.number = 10
    heads.count_photo(session, PNG)
    assert len(rows(db)) == 1
    assert heads.result(session) == {"count": 10, "marks": 10, "gap": 0, "alert": False}


# TC-68: the real model is in app/models, loads, and finds nobody in a black picture.
def test_real_counter_loads_tc68():
    assert PeopleCounter().count(np.zeros((600, 800, 3), np.uint8)) == 0
