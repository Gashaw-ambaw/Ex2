"""Tests of the photo upload on the Class page and the result line on Review (F1), with a fake counter."""
from contextlib import closing
from datetime import datetime, timezone

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import create_app

NOON = datetime(2026, 11, 28, 12, 0, 0, tzinfo=timezone.utc)
PNG = cv2.imencode(".png", np.zeros((40, 60, 3), np.uint8))[1].tobytes()


class FakeCounter:
    number = 0
    error = None

    def count(self, image):
        if self.error:
            raise self.error
        return self.number


@pytest.fixture
def counter():
    return FakeCounter()


@pytest.fixture
def app(settings, counter):
    app = create_app(settings, counter=counter)
    app.state.clock.set(NOON)
    return app


@pytest.fixture
def client(app):
    return TestClient(app, base_url="https://testserver", follow_redirects=False)


@pytest.fixture
def lecturer(client):
    assert client.post("/login", data={"password": "test-password"}).status_code == 303
    return client


def make_class(app, marks, closed=True):
    app.state.roster.save(
        [{"first_name": "Test", "last_name": str(i), "email": f"s{i}@example.com"} for i in range(marks)])
    attendance = app.state.attendance
    session = attendance.start_class()["id"]
    for entry in app.state.roster.list_active():
        attendance.add_manual(session, entry["id"])
    attendance.open_window(session)
    if closed:
        attendance.close_window(session)
    return session


def upload(client, data=PNG):
    return client.post("/class/photo", files={"photo": ("class.png", data, "image/png")})


def rows(app):
    with closing(app.state.db.connect()) as conn:
        return [tuple(r) for r in conn.execute("SELECT count, marks_at_count, gap, alert FROM head_counts")]


def table_part(text):
    return text.split("<table>")[1].split("</table>")[0]


# TC-27: 104 marks, 97 counted: the alert, flagged marks first, numbers stored, no photo kept.
def test_alert_on_review_tc27(app, lecturer, counter, tmp_path):
    session = make_class(app, 104)
    last = app.state.roster.list_active()[-1]
    app.state.attendance.add_flags(session, last["id"], "device-x", ["location"])
    counter.number = 97
    files_before = sorted(p.name for p in tmp_path.iterdir())

    reply = upload(lecturer)

    assert reply.status_code == 303 and reply.headers["location"] == "/class/review"
    page = lecturer.get("/class/review").text
    assert "Marks 104, counted 97, gap 7. Check the flagged marks first." in page
    assert table_part(page).index(last["email"]) < table_part(page).index("s0@example.com")
    assert rows(app) == [(97, 104, 7, 1)]
    assert sorted(p.name for p in tmp_path.iterdir()) == files_before


def test_no_gap_on_review(app, lecturer, counter):
    make_class(app, 3)
    counter.number = 3
    upload(lecturer)
    page = lecturer.get("/class/review").text
    assert "No gap" in page and "counted" not in page


def test_review_without_a_photo_has_no_line(app, lecturer):
    make_class(app, 3)
    page = lecturer.get("/class/review").text
    assert "No gap" not in page and "counted" not in page


# TC-29: a bad or too large file: an error on the Class page, nothing stored.
@pytest.mark.parametrize("data", [b"not an image", PNG + b"0" * (10 * 1024 * 1024)], ids=["text", "too large"])
def test_bad_photo_tc29(app, lecturer, data):
    make_class(app, 3)
    reply = upload(lecturer, data)
    assert reply.status_code == 400 and "The photo must be an image of at most 10 MB." in reply.text
    assert rows(app) == []


def test_upload_without_a_file_tc29(app, lecturer):
    make_class(app, 3)
    reply = lecturer.post("/class/photo")
    assert reply.status_code == 400 and "The photo must be an image of at most 10 MB." in reply.text
    assert rows(app) == []


# TC-30: the counter fails.
def test_counter_fails_tc30(app, lecturer, counter):
    make_class(app, 3)
    counter.error = RuntimeError("model")
    reply = upload(lecturer)
    assert reply.status_code == 400 and "Counting failed. No count was stored." in reply.text
    assert rows(app) == []


# TC-32: a gap with no flagged mark: the alert, and the list is the same as before.
def test_gap_without_flags_tc32(app, lecturer, counter):
    make_class(app, 10)
    before = table_part(lecturer.get("/class/review").text)
    counter.number = 5
    upload(lecturer)
    page = lecturer.get("/class/review").text
    assert "Marks 10, counted 5, gap 5." in page
    assert table_part(page) == before


# TC-66: the upload needs a closed window.
def test_no_class_today_tc66(app, lecturer):
    reply = upload(lecturer)
    assert reply.status_code == 400 and "Start class first." in reply.text
    assert rows(app) == []


@pytest.mark.parametrize("opened", [False, True], ids=["never opened", "still open"])
def test_before_close_tc66(app, lecturer, opened):
    session = app.state.attendance.start_class()["id"]
    if opened:
        app.state.attendance.open_window(session)
    reply = upload(lecturer)
    assert reply.status_code == 400 and "Close attendance first." in reply.text
    assert rows(app) == []


def test_form_only_after_close_tc66(app, lecturer):
    session = app.state.attendance.start_class()["id"]
    assert 'action="/class/photo"' not in lecturer.get("/class").text
    app.state.attendance.open_window(session)
    assert 'action="/class/photo"' not in lecturer.get("/class").text
    app.state.attendance.close_window(session)
    assert 'action="/class/photo"' in lecturer.get("/class").text


def test_upload_needs_login_tc66(app, client):
    make_class(app, 1)
    reply = upload(client)
    assert reply.status_code == 303 and reply.headers["location"] == "/login"
    assert rows(app) == []
