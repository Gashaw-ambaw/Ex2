"""Tests of the lecturer Polls page and the poll on the student class page (F3, UC-08, UC-09)."""
from contextlib import closing
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

NOON = datetime(2026, 11, 27, 10, 0, 0, tzinfo=timezone.utc)
NO_QUESTION = "No question now. Refresh when the lecturer announces one"
THANKS = "Thanks. When the lecturer closes the poll, refresh to see the result"
FORM = {"question": "Which one is LIFO?", "option1": "Stack", "option2": "", "option3": "Queue", "option4": "",
        "correct": "1"}


@pytest.fixture
def app(settings):
    app = create_app(settings)
    app.state.clock.set(NOON)
    return app


def browser(app):
    return TestClient(app, base_url="https://testserver", follow_redirects=False)


@pytest.fixture
def student(app):
    return browser(app)


@pytest.fixture
def lecturer(app):
    client = browser(app)
    assert client.post("/login", data={"password": "test-password"}).status_code == 303
    return client


@pytest.fixture
def started(app):
    return app.state.attendance.start_class()["id"]


def rows(app, name):
    with closing(app.state.db.connect()) as conn:
        return [dict(r) for r in conn.execute(f"SELECT * FROM {name} ORDER BY rowid")]


def start_poll(lecturer, **changes):
    reply = lecturer.post("/polls/start", data={**FORM, **changes})
    assert (reply.status_code, reply.headers["location"]) == (303, "/polls")
    return lecturer


def poll_id(app):
    return rows(app, "polls")[-1]["id"]


def answer(client, app, option, poll=None):
    return client.post("/c/answer", data={"poll_id": poll or poll_id(app), "option": option})


def close(lecturer, app):
    assert lecturer.post("/polls/close", data={"poll_id": poll_id(app)}).status_code == 303


# ---- Student ----

def test_no_poll_says_no_question_tc60(student, started):
    assert NO_QUESTION in student.get("/c").text


def test_the_student_sees_the_question_and_answers_tc59(app, student, lecturer, started):
    start_poll(lecturer)
    page = student.get("/c").text
    assert "Which one is LIFO?" in page and "Stack" in page and "Queue" in page
    reply = answer(student, app, 0)
    assert (reply.status_code, reply.headers["location"]) == (303, "/c?answered=1")
    after = student.get("/c?answered=1").text
    assert THANKS in after and 'action="/c/answer"' not in after
    assert "Correct" not in after and "Right answer" not in after


def test_a_second_visit_or_answer_says_you_answered_tc61(app, student, lecturer, started):
    start_poll(lecturer)
    student.get("/c")
    answer(student, app, 0)
    assert "You answered" in student.get("/c").text
    reply = answer(student, app, 1)
    assert (reply.status_code, reply.headers["location"]) == (303, "/c")
    assert len(rows(app, "poll_answers")) == 1


@pytest.mark.parametrize("option, word", [(0, "Correct"), (1, "Wrong")])
def test_after_close_the_student_sees_correct_or_wrong_tc62(app, student, lecturer, started, option, word):
    start_poll(lecturer)
    student.get("/c")
    answer(student, app, option)
    close(lecturer, app)
    page = student.get("/c").text
    assert f">{word}<" in page and "Right answer:" in page and "Stack" in page


def test_a_student_who_did_not_answer_sees_the_right_answer_tc62(app, student, lecturer, started):
    start_poll(lecturer)
    close(lecturer, app)
    page = student.get("/c").text
    assert "Right answer:" in page and ">Wrong<" not in page and ">Correct<" not in page


def test_without_a_correct_option_the_student_sees_the_distribution_tc62(app, student, lecturer, started):
    start_poll(lecturer, correct="")
    answer(student, app, 1)
    close(lecturer, app)
    page = student.get("/c").text
    assert "Stack: 0" in page and "Queue: 1" in page and "Right answer:" not in page


def test_a_late_or_wrong_answer_says_not_accepted_tc62(app, student, lecturer, started):
    start_poll(lecturer)
    reply = answer(student, app, 7)
    assert reply.status_code == 400 and "Not accepted." in reply.text
    close(lecturer, app)
    reply = answer(student, app, 0)
    assert reply.status_code == 400 and "Not accepted." in reply.text
    assert rows(app, "poll_answers") == []


def test_an_answer_with_no_session_today_stores_nothing(app, student, lecturer, started):
    start_poll(lecturer)
    app.state.clock.set(NOON + timedelta(days=1))
    reply = answer(student, app, 0)
    assert reply.status_code == 400 and "Class has not started" in reply.text
    assert rows(app, "poll_answers") == []


def test_the_answer_row_has_no_device_or_student_tc63(app, student, lecturer, started):
    start_poll(lecturer)
    student.cookies.set("device", "device-123")
    assert answer(student, app, 0).status_code == 303  # no sign-in, the anon cookie is made here
    [row] = rows(app, "poll_answers")
    assert set(row) == {"poll_id", "anon_id", "option_index", "created_at"}
    assert row["anon_id"] == student.cookies["anon"] and "device-123" not in row.values()


# ---- Lecturer ----

def test_start_with_no_session_today_says_start_class_first_tc64(app, lecturer, started):
    app.state.clock.set(NOON + timedelta(days=1))
    reply = lecturer.post("/polls/start", data=FORM)
    assert reply.status_code == 400 and "Start class first." in reply.text
    assert rows(app, "polls") == []


@pytest.mark.parametrize("changes", [{"question": "  "}, {"option3": ""}, {"correct": "2"}, {"correct": "abc"}])
def test_a_bad_form_shows_the_error_tc56(app, lecturer, started, changes):
    reply = lecturer.post("/polls/start", data={**FORM, **changes})
    assert reply.status_code == 400 and "Write a question and 2 to 4 options." in reply.text
    assert rows(app, "polls") == []


def test_while_open_the_lecturer_sees_only_the_number_of_answers_tc65(app, student, lecturer, started):
    start_poll(lecturer)
    answer(student, app, 0)
    page = lecturer.get("/polls").text
    assert "Which one is LIFO?" in page and '<strong id="answered">1</strong> answered' in page
    assert "Votes" not in page and "Right:" not in page and "Wrong:" not in page and "Correct answer" not in page
    assert lecturer.get("/polls/state").json() == {"open": True, "answered": 1}


def test_the_open_poll_page_has_refresh_offline_and_close_tc58(app, lecturer, started):
    start_poll(lecturer)
    page = lecturer.get("/polls").text
    for part in ("Refresh now", "Offline", "/polls/state", "20000", 'action="/polls/close"'):
        assert part in page


def test_after_close_the_lecturer_sees_votes_and_right_wrong_tc59(app, student, lecturer, started):
    start_poll(lecturer)
    answer(student, app, 0)
    answer(browser(app), app, 1)
    close(lecturer, app)
    page = lecturer.get("/polls").text
    assert "Votes" in page and "Correct answer" in page
    assert "Right: <strong>1</strong>" in page and "Wrong: <strong>1</strong>" in page
    assert "/polls/state" not in page  # a closed poll is not polled
    assert lecturer.get("/polls/state").json()["votes"] == [1, 1]


def test_the_polls_page_without_a_poll(lecturer):
    assert 'action="/polls/start"' in lecturer.get("/polls").text
    assert lecturer.get("/polls/state").json() == {"open": False, "answered": 0}


def test_the_nav_has_polls(lecturer):
    assert 'href="/polls"' in lecturer.get("/class").text


@pytest.mark.parametrize(
    "method, path", [("get", "/polls"), ("get", "/polls/state"), ("post", "/polls/start"), ("post", "/polls/close")]
)
def test_lecturer_poll_routes_need_the_password_tc53(app, student, method, path):
    reply = getattr(student, method)(path)
    assert (reply.status_code, reply.headers["location"]) == (303, "/login")
    assert rows(app, "polls") == []
