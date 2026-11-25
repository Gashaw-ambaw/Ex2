from contextlib import closing
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import pytest
from authlib.integrations.base_client import OAuthError
from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient

from app.main import create_app

NOON = datetime(2026, 11, 24, 12, 0, 0, tzinfo=timezone.utc)
DANA = {"first_name": "Dana", "last_name": "Levi", "email": "dana@example.com"}
RON = {"first_name": "Ron", "last_name": "Cohen", "email": "ron@example.com"}


class FakeGoogle:
    """Stands in for Google. The test sets which account "signs in". No network."""

    def __init__(self):
        self.email = "dana@example.com"
        self.verified = True
        self.error = None

    async def authorize_redirect(self, request, redirect_uri):
        return RedirectResponse("https://accounts.example/auth")

    async def authorize_access_token(self, request):
        if self.error:
            raise OAuthError(self.error)
        return {"userinfo": {"email": self.email, "email_verified": self.verified}}


@pytest.fixture
def google():
    return FakeGoogle()


@pytest.fixture
def app(settings, google):
    app = create_app(settings, google=google)
    app.state.clock.set(NOON)
    app.state.roster.save([DANA, RON])
    return app


def browser(app):
    # Each TestClient has its own cookies, so it is one phone.
    return TestClient(app, base_url="https://testserver", follow_redirects=False)


@pytest.fixture
def student(app):
    return browser(app)


@pytest.fixture
def lecturer(app):
    client = browser(app)
    assert client.post("/login", data={"password": "test-password"}).status_code == 303
    return client


def open_class(app):
    attendance = app.state.attendance
    session = attendance.start_class()
    attendance.open_window(session["id"])
    return session["id"]


def scan_path(app, session_id):
    url = urlparse(app.state.attendance.current_qr(session_id))
    return f"{url.path}?{url.query}"


def register(client, app, session_id):
    # The whole student flow up to the Confirm tap. Returns the reply of POST /register.
    assert client.get(scan_path(app, session_id)).status_code == 200
    assert client.get("/auth/start").status_code == 307
    assert client.get("/auth/callback").status_code == 200
    return client.post("/register")


def table(app, name):
    with closing(app.state.db.connect()) as conn:
        return [tuple(r) for r in conn.execute(f"SELECT * FROM {name} ORDER BY 1").fetchall()]


# ---- /scan ----

def test_scan_before_the_class_starts(student):
    reply = student.get("/scan?s=1&w=1&t=abc")
    assert reply.status_code == 400
    assert "Class has not started" in reply.text


def test_scan_with_a_bad_code(app, student):
    sid = open_class(app)
    reply = student.get(f"/scan?s={sid}&w=1&t=abc")
    assert reply.status_code == 400
    assert "Scan again" in reply.text


def test_scan_after_close_tc08(app, student):
    sid = open_class(app)
    path = scan_path(app, sid)
    app.state.attendance.close_window(sid)
    reply = student.get(path)
    assert reply.status_code == 400
    assert "Attendance is closed" in reply.text


def test_scan_after_the_window_ends_tc09(app, student):
    sid = open_class(app)
    path = scan_path(app, sid)
    app.state.clock.set(NOON + timedelta(seconds=300))
    assert "Attendance is closed" in student.get(path).text


def test_scan_of_an_unregistered_browser_offers_google_sign_in(app, student):
    sid = open_class(app)
    page = student.get(scan_path(app, sid))
    assert page.status_code == 200
    assert "Sign in with Google" in page.text
    assert 'href="/auth/start"' in page.text


# ---- /auth/start and /auth/callback ----

def test_sign_in_needs_a_scan_first(student):
    reply = student.get("/auth/start")
    assert reply.status_code == 400
    assert "Scan the QR in class first" in reply.text


def test_sign_in_goes_to_google(app, student):
    sid = open_class(app)
    student.get(scan_path(app, sid))
    reply = student.get("/auth/start")
    assert reply.status_code == 307
    assert reply.headers["location"].startswith("https://accounts.example/")


def test_callback_shows_the_email_and_writes_nothing(app, student):
    sid = open_class(app)
    student.get(scan_path(app, sid))
    before = (table(app, "devices"), table(app, "flags"), table(app, "roster_entries"))
    page = student.get("/auth/callback")
    assert page.status_code == 200
    assert "dana@example.com" in page.text
    assert "Confirm registration" in page.text
    assert 'action="/register"' in page.text
    assert (table(app, "devices"), table(app, "flags"), table(app, "roster_entries")) == before


# TC-16: the student cancels at Google.
def test_cancel_at_google_registers_nothing_tc16(app, student, google):
    sid = open_class(app)
    student.get(scan_path(app, sid))
    google.error = "access_denied"
    page = student.get("/auth/callback")
    assert page.status_code == 400 and "cancelled" in page.text
    assert table(app, "devices") == []
    # Without a verified email, Confirm does nothing either.
    assert student.post("/register").status_code == 400
    assert table(app, "devices") == []


def test_unverified_google_email_is_refused(app, student, google):
    sid = open_class(app)
    student.get(scan_path(app, sid))
    google.verified = False
    page = student.get("/auth/callback")
    assert page.status_code == 400
    assert "Confirm registration" not in page.text
    assert student.post("/register").status_code == 400


# ---- POST /register ----

# TC-14: Confirm registration links the browser; "Hello name"; the next scan skips Google.
def test_register_and_scan_again_tc14(app, student):
    sid = open_class(app)
    reply = register(student, app, sid)
    assert reply.status_code == 200
    assert "Hello Dana" in reply.text and "registered" in reply.text
    assert len(table(app, "devices")) == 1
    again = student.get(scan_path(app, sid))
    assert "Hello Dana" in again.text
    assert "Sign in with Google" not in again.text


def test_device_cookie_attributes(app, student, settings):
    sid = open_class(app)
    reply = register(student, app, sid)
    cookie = next(v for k, v in reply.headers.multi_items() if k == "set-cookie" and v.startswith("device="))
    lowered = cookie.lower()
    assert "httponly" in lowered and "secure" in lowered and "samesite=lax" in lowered
    assert f"max-age={settings.browser_cookie_days * 86400}" in lowered
    # The cookie value is the device id stored in the database.
    assert cookie.split(";")[0].split("=", 1)[1] == table(app, "devices")[0][0]


# TC-17: an email that is not on the roster.
def test_email_not_on_the_roster_tc17(app, student, google):
    sid = open_class(app)
    google.email = "stranger@example.com"
    reply = register(student, app, sid)
    assert reply.status_code == 400
    assert "Contact the lecturer" in reply.text
    assert "device=" not in reply.headers.get("set-cookie", "")
    assert table(app, "devices") == []


# TC-20: the ticket is older than SUBMIT_SEC after the sign-in.
def test_scan_expired_during_sign_in_tc20(app, student):
    sid = open_class(app)
    student.get(scan_path(app, sid))
    student.get("/auth/start")
    student.get("/auth/callback")
    app.state.clock.set(NOON + timedelta(seconds=61))
    reply = student.post("/register")
    assert reply.status_code == 200
    assert "registered" in reply.text and "Scan the QR again" in reply.text
    assert "Hello Dana" not in reply.text
    # The device is registered, so the next scan goes straight to Hello.
    assert len(table(app, "devices")) == 1
    assert "Hello Dana" in student.get(scan_path(app, sid)).text


def test_ticket_of_exactly_submit_sec_is_still_fresh(app, student):
    sid = open_class(app)
    student.get(scan_path(app, sid))
    student.get("/auth/start")
    student.get("/auth/callback")
    app.state.clock.set(NOON + timedelta(seconds=60))
    assert "Hello Dana" in student.post("/register").text


def test_register_needs_a_scan_and_a_sign_in(app, student):
    assert student.post("/register").status_code == 400
    sid = open_class(app)
    student.get(scan_path(app, sid))
    assert student.post("/register").status_code == 400  # scanned, but not signed in
    assert table(app, "devices") == []


def test_register_twice_does_not_repeat(app, student):
    sid = open_class(app)
    register(student, app, sid)
    assert student.post("/register").status_code == 400
    assert len(table(app, "devices")) == 1


# ---- Flags (D16): the controller passes the events to AttendanceService ----

def test_second_device_of_the_same_student_gets_a_new_device_flag(app):
    sid = open_class(app)
    register(browser(app), app, sid)
    assert app.state.attendance.window_state(sid).flags == 0
    register(browser(app), app, sid)
    flags = table(app, "flags")
    assert len(flags) == 1
    assert (flags[0][1], flags[0][4]) == (sid, "new_device")
    assert len(table(app, "devices")) == 2


def test_browser_of_another_student_gets_a_relinked_flag(app, google):
    sid = open_class(app)
    phone = browser(app)
    register(phone, app, sid)
    google.email = "ron@example.com"
    register(phone, app, sid)
    assert [f[4] for f in table(app, "flags")] == ["relinked"]
    assert len(table(app, "devices")) == 1  # the same browser, now linked to Ron
    assert "Hello Ron" in phone.get(scan_path(app, sid)).text


# ---- Roster forms (UC-05 5a, 5c) ----

def test_roster_forms_need_login(student):
    for path in ("/roster/add", "/roster/email"):
        reply = student.post(path, data={})
        assert reply.status_code == 303 and reply.headers["location"] == "/login"


def test_add_a_student_by_hand(app, lecturer):
    reply = lecturer.post("/roster/add", data={"first_name": "Noa", "last_name": "Bar", "email": "noa@example.com"})
    assert reply.status_code == 303 and reply.headers["location"] == "/roster?done=added"
    assert "Student added" in lecturer.get("/roster?done=added").text
    assert app.state.roster.find_by_email("noa@example.com")["source"] == "manual"


def test_add_a_student_with_a_bad_email_shows_an_error(lecturer):
    reply = lecturer.post("/roster/add", data={"first_name": "Noa", "last_name": "Bar", "email": "bad"})
    assert reply.status_code == 400
    assert 'class="error"' in reply.text


def test_add_an_existing_student_shows_an_error(lecturer):
    reply = lecturer.post("/roster/add", data={"first_name": "X", "last_name": "Y", "email": "dana@example.com"})
    assert reply.status_code == 400 and "already" in reply.text


def test_an_added_student_can_register(app, lecturer, student, google):
    # UC-03 3b: the student is not on the roster, the lecturer adds the entry, the student tries again.
    sid = open_class(app)
    google.email = "noa@example.com"
    assert register(student, app, sid).status_code == 400
    lecturer.post("/roster/add", data={"first_name": "Noa", "last_name": "Bar", "email": "noa@example.com"})
    reply = register(student, app, sid)
    assert reply.status_code == 200 and "Hello Noa" in reply.text


# TC-38: edit a roster email; sign-in with the new email matches the entry.
def test_edit_email_then_sign_in_with_the_new_email_tc38(app, lecturer, student, google):
    reply = lecturer.post("/roster/email", data={"current_email": "dana@example.com", "new_email": "dana.real@gmail.com"})
    assert reply.status_code == 303 and reply.headers["location"] == "/roster?done=email"
    assert "Email changed" in lecturer.get("/roster?done=email").text
    sid = open_class(app)
    google.email = "dana.real@gmail.com"
    reply = register(student, app, sid)
    assert reply.status_code == 200 and "Hello Dana" in reply.text


def test_edit_email_errors(lecturer):
    unknown = lecturer.post("/roster/email", data={"current_email": "nobody@example.com", "new_email": "a@example.com"})
    assert unknown.status_code == 400 and 'class="error"' in unknown.text
    taken = lecturer.post("/roster/email", data={"current_email": "dana@example.com", "new_email": "ron@example.com"})
    assert taken.status_code == 400 and "another" in taken.text
    bad = lecturer.post("/roster/email", data={"current_email": "dana@example.com", "new_email": "nope"})
    assert bad.status_code == 400


def test_roster_page_has_the_two_forms(lecturer):
    page = lecturer.get("/roster").text
    assert 'action="/roster/add"' in page and 'action="/roster/email"' in page
