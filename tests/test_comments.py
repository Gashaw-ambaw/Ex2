"""CommentService (F2, FR-08, FR-09): TC-47, TC-49, TC-50, TC-51."""
from contextlib import closing
from datetime import datetime, timedelta, timezone

import pytest

from app.attendance import AttendanceService
from app.comments import CommentService
from app.qr_tokens import QrTokens

NOON = datetime(2026, 11, 27, 10, 0, 0, tzinfo=timezone.utc)
LENGTH_ERROR = "Write 1 to 300 characters."


@pytest.fixture
def attendance(db, clock, settings):
    clock.set(NOON)
    return AttendanceService(db, clock, settings, QrTokens(settings.secret_key, settings.qr_rotate_sec, clock))


@pytest.fixture
def comments(db, clock, settings):
    return CommentService(db, clock, settings)


@pytest.fixture
def session(attendance):
    return attendance.start_class()["id"]


def rows(db):
    with closing(db.connect()) as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM comments ORDER BY id")]


def test_a_comment_is_stored_with_session_browser_id_and_time_tc47(db, comments, session):
    comments.send(session, "anon-a", "  Please repeat the last topic  ")
    [row] = rows(db)
    assert (row["session_id"], row["anon_id"]) == (session, "anon-a")
    assert row["text"] == "Please repeat the last topic"
    assert row["created_at"] == "2026-11-27T10:00:00+00:00"


def test_a_browser_sees_only_its_own_comments_of_the_session_newest_first_tc47(attendance, comments, clock, session):
    comments.send(session, "anon-a", "first")
    comments.send(session, "anon-b", "someone else")
    clock.set(NOON + timedelta(seconds=20))
    comments.send(session, "anon-a", "second")
    other = attendance.new_session("Tutorial")["id"]
    clock.set(NOON + timedelta(seconds=40))
    comments.send(other, "anon-a", "other session")
    own = comments.own("anon-a", session)
    assert [c["text"] for c in own] == ["second", "first"]
    assert own[0]["time"] == "12:00"  # Israel time


def test_the_lecturer_list_has_all_comments_of_the_session_newest_first_tc52(comments, session):
    comments.send(session, "anon-a", "first")
    comments.send(session, "anon-b", "second")
    assert [c["text"] for c in comments.list_for_lecturer(session)] == ["second", "first"]


@pytest.mark.parametrize("text", ["", "   \n\t ", "x" * 301])
def test_empty_spaces_only_or_too_long_is_refused_tc49(db, comments, session, text):
    with pytest.raises(ValueError, match=LENGTH_ERROR):
        comments.send(session, "anon-a", text)
    assert rows(db) == []


def test_exactly_300_characters_are_accepted_tc49(db, comments, session):
    # A line break arrives from a browser form as two characters; it counts as one.
    comments.send(session, "anon-a", "x" * 149 + "\r\n" + "y" * 150)
    assert len(rows(db)[0]["text"]) == 300


def test_a_second_comment_after_9_seconds_is_refused_tc50(db, comments, clock, session):
    comments.send(session, "anon-a", "first")
    clock.set(NOON + timedelta(seconds=9))
    with pytest.raises(ValueError, match="Wait a moment."):
        comments.send(session, "anon-a", "second")
    assert len(rows(db)) == 1


def test_a_second_comment_after_10_seconds_is_accepted_tc50(db, comments, clock, session):
    comments.send(session, "anon-a", "first")
    clock.set(NOON + timedelta(seconds=10))
    comments.send(session, "anon-a", "second")
    assert len(rows(db)) == 2


def test_the_limit_is_per_browser_tc50(db, comments, session):
    comments.send(session, "anon-a", "first")
    comments.send(session, "anon-b", "first")
    assert len(rows(db)) == 2


def test_after_close_and_after_a_new_session_a_comment_goes_to_todays_latest_tc51(attendance, comments, clock, session):
    attendance.open_window(session)
    attendance.close_window(session)
    comments.send(attendance.session_for_today()["id"], "anon-a", "after close")
    tutorial = attendance.new_session("Tutorial")["id"]
    clock.set(NOON + timedelta(seconds=30))
    comments.send(attendance.session_for_today()["id"], "anon-a", "in the tutorial")
    assert [c["text"] for c in comments.list_for_lecturer(session)] == ["after close"]
    assert [c["text"] for c in comments.list_for_lecturer(tutorial)] == ["in the tutorial"]


def test_an_earlier_date_is_never_todays_session_tc51(attendance, clock, session):
    clock.set(NOON + timedelta(days=1))
    assert attendance.session_for_today() is None
