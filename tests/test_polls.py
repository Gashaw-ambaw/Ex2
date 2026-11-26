"""Tests of PollService (F3): starting, answering, closing and the results of a poll."""
from contextlib import closing
from datetime import datetime, timedelta, timezone

import pytest

from app.attendance import AttendanceService
from app.polls import PollService
from app.qr_tokens import QrTokens

NOON = datetime(2026, 11, 27, 10, 0, 0, tzinfo=timezone.utc)
POLL_ERROR = "Write a question and 2 to 4 options."
FOUR_FIELDS = ["Stack", "Queue", "", ""]


@pytest.fixture
def attendance(db, clock, settings):
    clock.set(NOON)
    return AttendanceService(db, clock, settings, QrTokens(settings.secret_key, settings.qr_rotate_sec, clock))


@pytest.fixture
def polls(db, clock, settings):
    return PollService(db, clock, settings)


@pytest.fixture
def session(attendance):
    return attendance.start_class()["id"]


def table(db, name):
    with closing(db.connect()) as conn:
        return [dict(r) for r in conn.execute(f"SELECT * FROM {name} ORDER BY rowid")]


def start(polls, session, question="Which one is LIFO?", options=FOUR_FIELDS, correct=0):
    return polls.start(session, question, list(options), correct)


def test_a_started_poll_is_the_active_poll_of_the_session_tc55(polls, session):
    poll_id = start(polls, session, question="  Which one is LIFO?  ")
    poll = polls.active(session)
    assert (poll["id"], poll["question"], poll["options"]) == (poll_id, "Which one is LIFO?", ["Stack", "Queue"])
    assert (poll["correct"], poll["open"]) == (0, True)


def test_answers_are_counted_and_the_votes_appear_after_close_tc55(polls, session):
    poll_id = start(polls, session)
    assert polls.answer(session, poll_id, "anon-a", 0) == "ok"
    assert polls.answer(session, poll_id, "anon-b", 1) == "ok"
    assert polls.results(poll_id) == {"open": True, "answered": 2}
    polls.close(poll_id)
    assert polls.results(poll_id) == {
        "open": False, "answered": 2, "votes": [1, 1], "correct": 0, "right": 1, "wrong": 1,
    }
    assert polls.active(session)["open"] is False
    assert (polls.answer_of(poll_id, "anon-b"), polls.answer_of(poll_id, "anon-x")) == (1, None)


def test_while_open_the_results_never_have_votes_or_the_correct_answer_tc65(polls, session):
    poll_id = start(polls, session)
    polls.answer(session, poll_id, "anon-a", 0)
    assert set(polls.results(poll_id)) == {"open", "answered"}


@pytest.mark.parametrize(
    "question, options, correct",
    [
        ("", ["A", "B"], None),
        ("   ", ["A", "B"], None),  # only spaces counts as empty
        ("Q", ["A", "  ", "", ""], None),  # 1 option
        ("Q", ["A", "B", "C", "D", "E"], None),  # 5 options
        ("Q", ["A", "", "C", ""], 1),  # correct marked on a blank field
        ("Q", ["A", "B"], 7),
        ("Q", ["A", "B"], -1),
    ],
)
def test_a_bad_poll_is_refused_and_nothing_changes_tc56(db, polls, session, question, options, correct):
    first = start(polls, session)
    with pytest.raises(ValueError, match=POLL_ERROR):
        polls.start(session, question, options, correct)
    assert [(p["id"], p["status"]) for p in table(db, "polls")] == [(first, "open")]


def test_blank_fields_are_dropped_and_correct_stays_with_its_text_tc56(polls, session):
    start(polls, session, options=["First", "", "Third", ""], correct=2)
    poll = polls.active(session)
    assert poll["options"] == ["First", "Third"]
    assert poll["options"][poll["correct"]] == "Third"


def test_a_new_poll_closes_the_open_one_and_keeps_its_results_tc57(db, polls, session):
    first = start(polls, session)
    polls.answer(session, first, "anon-a", 1)
    second = start(polls, session, question="Second?")
    assert [p["status"] for p in table(db, "polls")] == ["closed", "open"]
    assert polls.results(first)["votes"] == [0, 1]
    assert polls.active(session)["id"] == second


def test_a_poll_left_open_on_an_earlier_day_is_closed_too_tc57(db, attendance, polls, clock, session):
    old = start(polls, session)
    clock.set(NOON + timedelta(days=1))
    today = attendance.start_class()["id"]
    new = start(polls, today)
    assert [(p["id"], p["status"]) for p in table(db, "polls")] == [(old, "closed"), (new, "open")]


def test_without_a_correct_option_the_results_are_the_distribution_tc59(polls, session):
    poll_id = start(polls, session, correct=None)
    polls.answer(session, poll_id, "anon-a", 1)
    polls.close(poll_id)
    assert polls.results(poll_id) == {"open": False, "answered": 1, "votes": [0, 1]}


def test_a_second_answer_of_a_browser_is_not_stored_tc61(db, polls, session):
    poll_id = start(polls, session)
    polls.answer(session, poll_id, "anon-a", 0)
    assert polls.answer(session, poll_id, "anon-a", 1) == "already"
    assert [(r["anon_id"], r["option_index"]) for r in table(db, "poll_answers")] == [("anon-a", 0)]


def test_an_answer_after_close_is_not_accepted_tc62(db, polls, session):
    poll_id = start(polls, session)
    polls.close(poll_id)
    assert polls.answer(session, poll_id, "anon-a", 0) == "not accepted"
    assert table(db, "poll_answers") == []


@pytest.mark.parametrize("option", [-1, 2, 99])
def test_an_option_that_does_not_exist_is_not_accepted_tc62(db, polls, session, option):
    poll_id = start(polls, session)
    assert polls.answer(session, poll_id, "anon-a", option) == "not accepted"
    assert table(db, "poll_answers") == []


def test_an_old_poll_or_an_unknown_poll_is_not_accepted_tc62(polls, session):
    old = start(polls, session)
    start(polls, session, question="Second?")
    assert polls.answer(session, old, "anon-a", 0) == "not accepted"
    assert polls.answer(session, 999, "anon-a", 0) == "not accepted"


def test_an_open_poll_of_an_earlier_session_is_not_accepted_tc62(attendance, polls, session):
    old = start(polls, session)
    tutorial = attendance.new_session("Tutorial")["id"]
    assert polls.active(tutorial) is None
    assert polls.answer(tutorial, old, "anon-a", 0) == "not accepted"
