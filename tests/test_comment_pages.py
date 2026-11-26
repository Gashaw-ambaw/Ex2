"""The class page /c and the lecturer pages for comments (UC-06, UC-07), through the test client."""
from contextlib import closing
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

NOON = datetime(2026, 11, 27, 10, 0, 0, tzinfo=timezone.utc)
NOT_STARTED = "Class has not started"


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


def rows(app):
    with closing(app.state.db.connect()) as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM comments ORDER BY id")]


def send(client, text):
    return client.post("/c/comment", data={"text": text})


# ---- The student class page ----

def test_a_sent_comment_shows_sent_and_appears_in_the_own_list_tc47(app, student, started):
    assert "<textarea" in student.get("/c").text
    reply = send(student, "Please repeat")
    assert (reply.status_code, reply.headers["location"]) == (303, "/c?sent=1")
    page = student.get(reply.headers["location"]).text
    assert "Sent" in page and "Please repeat" in page


def test_another_browser_does_not_see_the_comment_tc47(app, student, started):
    student.get("/c")
    send(student, "Please repeat")
    assert "Please repeat" not in browser(app).get("/c").text


def test_without_a_session_today_the_page_says_not_started_tc48(app, student):
    page = student.get("/c")
    assert page.status_code == 200 and NOT_STARTED in page.text and "<textarea" not in page.text
    reply = send(student, "Hello")
    assert reply.status_code == 400 and NOT_STARTED in reply.text
    assert rows(app) == []


def test_yesterdays_session_does_not_count_tc48(app, student, started):
    app.state.clock.set(NOON + timedelta(days=1))
    assert NOT_STARTED in student.get("/c").text
    send(student, "Hello")
    assert rows(app) == []


def test_a_refused_comment_keeps_the_text_tc49(app, student, started):
    student.get("/c")
    long_text = "x" * 301
    reply = send(student, long_text)
    assert reply.status_code == 400
    assert "Write 1 to 300 characters." in reply.text and long_text in reply.text
    send(student, "first")
    reply = send(student, "too soon")
    assert "Wait a moment." in reply.text and "too soon</textarea>" in reply.text


def test_comment_text_is_shown_as_text_not_html_tc47(app, student, started):
    send(student, "<b>bold</b>")
    assert "<b>bold</b>" not in student.get("/c").text


def test_the_anon_cookie_is_separate_and_no_identity_is_stored_tc63(app, student, started):
    reply = student.get("/c")  # no sign-in
    assert reply.status_code == 200
    cookie = reply.headers["set-cookie"].lower()
    assert cookie.startswith("anon=")
    for part in ("httponly", "secure", "samesite=lax", "max-age=10368000"):
        assert part in cookie
    assert "device=" not in cookie
    anon = student.cookies["anon"]
    assert "set-cookie" not in student.get("/c").headers  # kept, not replaced
    student.cookies.set("device", "device-123")
    send(student, "Hello")
    [row] = rows(app)
    assert row["anon_id"] == anon and "device-123" not in row.values()
    assert set(row) == {"id", "session_id", "anon_id", "text", "hidden", "created_at"}


def test_a_post_without_the_cookie_creates_one_tc63(app, student, started):
    reply = send(student, "Hello")
    assert reply.status_code == 303
    assert rows(app)[0]["anon_id"] == student.cookies["anon"]


# ---- Lecturer pages ----

def test_the_class_link_page_shows_the_fixed_qr_and_the_link_tc63(app, lecturer, started):
    assert 'action="/class/link"' in lecturer.get("/class").text
    page = lecturer.get("/class/link").text
    assert "https://example.test/c<" in page and "<svg" in page


def test_the_comments_page_has_refresh_and_offline_tc52(app, lecturer):
    page = lecturer.get("/comments").text
    assert "Refresh now" in page and "Offline" in page and "/comments/state" in page
    assert "20000" in page  # REFRESH_SEC


def test_the_state_lists_the_latest_sessions_comments_newest_first_tc52(app, lecturer, student, started):
    assert lecturer.get("/comments/state").json()["comments"] == []
    send(student, "first")
    app.state.clock.set(NOON + timedelta(seconds=15))
    send(student, "second")
    app.state.clock.set(NOON + timedelta(days=1))  # still shown the next day (latest session)
    state = lecturer.get("/comments/state").json()
    assert state["session"] == "2026-11-27"
    assert state["comments"] == [{"time": "12:00", "text": "second"}, {"time": "12:00", "text": "first"}]


def test_the_state_without_any_session_tc52(app, lecturer):
    assert lecturer.get("/comments/state").json() == {"session": None, "comments": []}


@pytest.mark.parametrize("path", ["/comments", "/comments/state", "/class/link"])
def test_lecturer_comment_pages_need_the_password_tc53(student, path):
    reply = student.get(path)
    assert (reply.status_code, reply.headers["location"]) == (303, "/login")
