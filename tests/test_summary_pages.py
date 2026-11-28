"""Tests of the Summary page (F4): password, upload, processing, failed and done, with a fake model."""
from contextlib import closing
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

NOON = datetime(2026, 11, 28, 12, 0, 0, tzinfo=timezone.utc)
VTT = b"WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHello class.\n"
HINT = "Upload a VTT or txt transcript."
REFRESH = '<meta http-equiv="refresh" content="20">'


class FakeLlm:
    configured = True
    reply = "A short <summary>."
    error = None

    def complete(self, instructions, data_text):
        if self.error:
            raise self.error
        return self.reply


class Spawn:
    """Runs the job at once, or keeps it waiting (hold = True)."""
    hold = False

    def __call__(self, work):
        if not self.hold:
            work()


@pytest.fixture
def llm():
    return FakeLlm()


@pytest.fixture
def spawn():
    return Spawn()


def make_app(settings, **parts):
    app = create_app(settings, **parts)
    app.state.clock.set(NOON)
    return app


@pytest.fixture
def app(settings, llm, spawn):
    return make_app(settings, llm=llm, spawn=spawn)


def sign_in(app):
    client = TestClient(app, base_url="https://testserver", follow_redirects=False)
    assert client.post("/login", data={"password": "test-password"}).status_code == 303
    return client


@pytest.fixture
def lecturer(app):
    return sign_in(app)


def upload(client, data=VTT, name="lecture.vtt"):
    return client.post("/summary", files={"transcript": (name, data, "text/vtt")})


def count(app, table):
    with closing(app.state.db.connect()) as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


# TC-76: the page needs the password.
def test_needs_login_tc76(app):
    app.state.attendance.start_class()
    client = TestClient(app, base_url="https://testserver", follow_redirects=False)
    for reply in (client.get("/summary"), upload(client)):
        assert reply.status_code == 303 and reply.headers["location"] == "/login"
    assert count(app, "jobs") == 0


def test_no_class_tc76(app, lecturer):
    assert "Start class first." in lecturer.get("/summary").text
    reply = upload(lecturer)
    assert reply.status_code == 400 and "Start class first." in reply.text
    assert count(app, "jobs") == 0


def test_no_key_tc76(settings):
    app = make_app(settings)
    app.state.attendance.start_class()
    lecturer = sign_in(app)
    page = lecturer.get("/summary").text
    assert "Summary is not set up." in page and 'action="/summary"' not in page
    reply = upload(lecturer)
    assert reply.status_code == 400 and "Summary is not set up." in reply.text
    assert count(app, "jobs") == 0


def test_form_and_menu_tc76(app, lecturer):
    app.state.attendance.start_class()
    page = lecturer.get("/summary").text
    assert 'action="/summary"' in page and HINT in page and REFRESH not in page
    assert '<a href="/summary">Summary</a>' in page


def test_upload_then_summary_tc76(app, lecturer):
    app.state.attendance.start_class()
    reply = upload(lecturer)
    assert reply.status_code == 303 and reply.headers["location"] == "/summary"
    page = lecturer.get("/summary").text
    assert "A short &lt;summary&gt;." in page and REFRESH not in page
    assert "Failed" not in page


def test_processing_tc76(app, lecturer, spawn):
    app.state.attendance.start_class()
    spawn.hold = True
    upload(lecturer)
    page = lecturer.get("/summary").text
    assert "Processing" in page and REFRESH in page and 'action="/summary"' not in page
    reply = upload(lecturer)
    assert reply.status_code == 400 and "A summary is already running." in reply.text


def test_latest_session_tc76(app, lecturer):
    attendance = app.state.attendance
    attendance.start_class()
    upload(lecturer)
    attendance.new_session("Tutorial")
    assert "A short" not in lecturer.get("/summary").text


# TC-70 through the page.
@pytest.mark.parametrize("data, name", [(b"%PDF", "a.pdf"), (b"x" * (2 * 1024 * 1024 + 1), "a.txt")],
                         ids=["pdf", "too large"])
def test_bad_file_tc70(app, lecturer, data, name):
    app.state.attendance.start_class()
    reply = upload(lecturer, data, name)
    assert reply.status_code == 400
    assert "The file must be a VTT or txt transcript of at most 2 MB." in reply.text
    assert count(app, "jobs") == 0 and count(app, "summaries") == 0


def test_upload_without_a_file_tc70(app, lecturer):
    app.state.attendance.start_class()
    reply = lecturer.post("/summary")
    assert reply.status_code == 400 and f'<p class="error">{HINT}</p>' in reply.text
    assert count(app, "jobs") == 0


# TC-73 through the page.
def test_failed_tc73(app, lecturer, llm):
    app.state.attendance.start_class()
    llm.error = RuntimeError("model down")
    assert upload(lecturer).status_code == 303
    page = lecturer.get("/summary").text
    assert "Failed: upload again." in page and 'action="/summary"' in page
    assert "model down" not in page and count(app, "summaries") == 0


# TC-75 through the app: after a restart the old running job is shown as failed.
def test_restart_tc75(app, lecturer, settings, llm, spawn):
    app.state.attendance.start_class()
    spawn.hold = True
    upload(lecturer)
    again = sign_in(make_app(settings, llm=llm, spawn=spawn))
    assert "Failed: upload again." in again.get("/summary").text
