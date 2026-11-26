"""Tests of the lecturer Class and QR pages (F1): login, Start class, open, close, location."""
from contextlib import closing
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.attendance import CLOSED_MESSAGE
from app.main import create_app

NOON = datetime(2026, 11, 24, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def client(settings):
    return TestClient(create_app(settings), base_url="https://testserver", follow_redirects=False)


@pytest.fixture
def logged_in(client):
    client.app.state.clock.set(NOON)
    assert client.post("/login", data={"password": "test-password"}).status_code == 303
    return client


def snapshot(client):
    with closing(client.app.state.db.connect()) as conn:
        return [tuple(r) for r in conn.execute("SELECT * FROM class_sessions").fetchall()], [
            tuple(r) for r in conn.execute("SELECT * FROM class_location").fetchall()
        ]


def test_login_goes_to_the_class_page(client):
    reply = client.post("/login", data={"password": "test-password"})
    assert reply.status_code == 303 and reply.headers["location"] == "/class"


@pytest.mark.parametrize("method,path", [
    ("get", "/class"), ("get", "/class/qr"), ("get", "/class/state"),
    ("post", "/class/start"), ("post", "/class/open"), ("post", "/class/close"), ("post", "/class/location"),
])
def test_class_routes_need_login(client, method, path):
    reply = getattr(client, method)(path)
    assert reply.status_code == 303 and reply.headers["location"] == "/login"


def test_class_page_before_start(logged_in):
    page = logged_in.get("/class")
    assert page.status_code == 200
    assert "Class has not started" in page.text
    assert "No class location set" in page.text
    assert 'href="/roster"' in page.text


# TC-05: Start class, Open attendance: a QR, a countdown and a count of 0.
def test_start_and_open_tc05(logged_in):
    assert logged_in.post("/class/start").headers["location"] == "/class"
    reply = logged_in.post("/class/open")
    assert reply.status_code == 303 and reply.headers["location"] == "/class/qr"
    assert logged_in.get("/class/qr").status_code == 200
    state = logged_in.get("/class/state").json()
    assert state["open"] is True
    assert state["seconds_left"] == 300
    assert state["marks"] == 0
    assert state["qr_svg"].startswith("<svg")


def test_qr_page_polls_at_the_rotate_interval(logged_in):
    logged_in.post("/class/start")
    logged_in.post("/class/open")
    assert "setInterval(poll, 10000)" in logged_in.get("/class/qr").text


def test_qr_changes_with_the_window(logged_in):
    logged_in.post("/class/start")
    logged_in.post("/class/open")
    first = logged_in.get("/class/state").json()["qr_svg"]
    logged_in.app.state.clock.set(NOON + timedelta(seconds=10))
    assert logged_in.get("/class/state").json()["qr_svg"] != first


# TC-06: no session today.
def test_open_without_start_tc06(logged_in):
    reply = logged_in.post("/class/open")
    assert reply.status_code == 400
    assert "Start class first" in reply.text
    assert snapshot(logged_in)[0] == []


def test_state_without_a_session(logged_in):
    state = logged_in.get("/class/state").json()
    assert state["open"] is False and state["qr_svg"] is None


def test_qr_page_without_an_open_window_goes_back(logged_in):
    assert logged_in.get("/class/qr").headers["location"] == "/class"
    logged_in.post("/class/start")
    assert logged_in.get("/class/qr").headers["location"] == "/class"


# TC-08 (window side): close early, the totals are shown, the state is closed.
def test_close_early_tc08(logged_in):
    logged_in.post("/class/start")
    logged_in.post("/class/open")
    assert logged_in.post("/class/close").headers["location"] == "/class"
    page = logged_in.get("/class").text
    assert "Attendance is closed" in page and "Marks:" in page and "Flags:" in page
    state = logged_in.get("/class/state").json()
    assert state["open"] is False and state["qr_svg"] is None
    assert logged_in.get("/class/qr").headers["location"] == "/class"


# TC-09 (window side): the window ends by itself.
def test_window_ends_by_itself_tc09(logged_in):
    logged_in.post("/class/start")
    logged_in.post("/class/open")
    logged_in.app.state.clock.set(NOON + timedelta(seconds=300))
    state = logged_in.get("/class/state").json()
    assert state["open"] is False and state["qr_svg"] is None


# TC-45: a window that was already open once is not opened again.
@pytest.mark.parametrize("how", ["close", "expire"])
def test_open_again_is_refused_tc45(logged_in, how):
    logged_in.post("/class/start")
    logged_in.post("/class/open")
    if how == "close":
        logged_in.post("/class/close")
    else:
        logged_in.app.state.clock.set(NOON + timedelta(seconds=301))
    before = snapshot(logged_in)
    reply = logged_in.post("/class/open")
    assert reply.status_code == 400
    assert CLOSED_MESSAGE in reply.text
    assert snapshot(logged_in) == before


def test_open_while_open_goes_to_the_qr_page(logged_in):
    logged_in.post("/class/start")
    logged_in.post("/class/open")
    before = snapshot(logged_in)
    reply = logged_in.post("/class/open")
    assert reply.status_code == 303 and reply.headers["location"] == "/class/qr"
    assert snapshot(logged_in) == before


def test_state_writes_nothing(logged_in):
    logged_in.post("/class/start")
    logged_in.post("/class/open")
    before = snapshot(logged_in)
    logged_in.app.state.clock.set(NOON + timedelta(seconds=400))
    logged_in.get("/class/state")
    logged_in.get("/class")
    assert snapshot(logged_in) == before


# The class location (D28).
def test_save_location(logged_in):
    reply = logged_in.post("/class/location", data={"location": "32.08, 34.78"})
    assert reply.status_code == 303
    page = logged_in.get("/class").text
    assert "32.08, 34.78" in page
    assert "No class location set" not in page


@pytest.mark.parametrize("text", ["abc", "95, 10", "10, 200", ""])
def test_bad_location_is_refused(logged_in, text):
    reply = logged_in.post("/class/location", data={"location": text})
    assert reply.status_code == 400
    assert 'class="error"' in reply.text
    assert snapshot(logged_in)[1] == []


# UC-01 1b (D31): after a closed or expired window, the lecturer starts a new session.
def expire_or_close(client, how):
    client.post("/class/start")
    client.post("/class/open")
    if how == "close":
        client.post("/class/close")
    else:
        client.app.state.clock.set(NOON + timedelta(seconds=301))


@pytest.mark.parametrize("how", ["close", "expire"])
def test_new_session_after_a_closed_window_uc01_1b(logged_in, how):
    expire_or_close(logged_in, how)
    assert "Start a new session" in logged_in.get("/class").text
    reply = logged_in.post("/class/new", data={"name": "Tutorial"})
    assert reply.status_code == 303 and reply.headers["location"] == "/class"
    page = logged_in.get("/class").text
    assert "Tutorial" in page
    # The new session has no window yet, so Open attendance works again.
    reply = logged_in.post("/class/open")
    assert reply.status_code == 303 and reply.headers["location"] == "/class/qr"
    assert logged_in.get("/class/state").json()["open"] is True


def test_new_session_keeps_the_old_one(logged_in):
    expire_or_close(logged_in, "close")
    logged_in.post("/class/new", data={"name": ""})
    with closing(logged_in.app.state.db.connect()) as conn:
        assert conn.execute("SELECT COUNT(*) FROM class_sessions").fetchone()[0] == 2


def test_new_session_button_is_not_always_shown(logged_in):
    assert "Start a new session" not in logged_in.get("/class").text  # no session
    logged_in.post("/class/start")
    assert "Start a new session" not in logged_in.get("/class").text  # never opened
    logged_in.post("/class/open")
    assert "Start a new session" not in logged_in.get("/class").text  # open now


def test_tc45_page_offers_the_new_session_button(logged_in):
    expire_or_close(logged_in, "close")
    reply = logged_in.post("/class/open")
    assert reply.status_code == 400 and CLOSED_MESSAGE in reply.text
    assert "Start a new session" in reply.text


def test_new_session_is_refused_while_open(logged_in):
    logged_in.post("/class/start")
    logged_in.post("/class/open")
    reply = logged_in.post("/class/new", data={"name": "x"})
    assert reply.status_code == 400
    assert "Close attendance first" in reply.text
    with closing(logged_in.app.state.db.connect()) as conn:
        assert conn.execute("SELECT COUNT(*) FROM class_sessions").fetchone()[0] == 1


def test_new_session_name_is_escaped(logged_in):
    expire_or_close(logged_in, "close")
    logged_in.post("/class/new", data={"name": "<b>x</b>"})
    page = logged_in.get("/class").text
    assert "<b>x</b>" not in page and "&lt;b&gt;x&lt;/b&gt;" in page


def test_new_session_needs_login(client):
    reply = client.post("/class/new", data={"name": "x"})
    assert reply.status_code == 303 and reply.headers["location"] == "/login"
