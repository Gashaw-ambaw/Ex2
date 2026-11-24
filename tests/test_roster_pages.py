import csv
import html
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.roster import RosterService

SAMPLES = Path(__file__).parent.parent / "sample_data"


@pytest.fixture
def client(settings):
    # follow_redirects=False so a test can see the redirect itself.
    return TestClient(create_app(settings), base_url="https://testserver", follow_redirects=False)


@pytest.fixture
def logged_in(client):
    reply = client.post("/login", data={"password": "test-password"})
    assert reply.status_code == 303
    return client


def upload(client, name):
    data = (SAMPLES / name).read_bytes()
    return client.post("/roster/upload", files={"file": (name, data, "text/csv")})


def sample_rows():
    with open(SAMPLES / "roster.csv", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def active_count(client):
    app = client.app
    return len(RosterService(app.state.db, app.state.clock).list_active())


# TC-42: lecturer pages need the password.
def test_roster_page_needs_login(client):
    reply = client.get("/roster")
    assert reply.status_code == 303 and reply.headers["location"] == "/login"


def test_upload_and_confirm_need_login(client):
    assert client.post("/roster/upload", files={"file": ("a.csv", b"x")}).status_code == 303
    assert client.post("/roster/confirm", data={}).status_code == 303
    assert active_count(client) == 0


def test_right_password_opens_the_roster_page(logged_in):
    page = logged_in.get("/roster")
    assert page.status_code == 200
    assert "Roster" in page.text


def test_wrong_password_shows_a_message_and_no_access(client):
    reply = client.post("/login", data={"password": "nope"})
    assert reply.status_code == 200 and "Wrong password" in reply.text
    assert client.get("/roster").status_code == 303


# TC-42: after 5 wrong attempts login is locked, and the right password is refused too.
def test_lockout_after_five_wrong_attempts(client):
    for _ in range(5):
        reply = client.post("/login", data={"password": "nope"})
    assert "locked" in reply.text.lower()
    reply = client.post("/login", data={"password": "test-password"})
    assert reply.status_code == 200 and "locked" in reply.text.lower()
    assert client.get("/roster").status_code == 303


# Logout is a POST (D24) and closes the session.
def test_logout_closes_the_session(logged_in):
    assert logged_in.post("/logout").status_code == 303
    assert logged_in.get("/roster").status_code == 303


# The roster page has a logout button (EDD 6).
def test_roster_page_has_a_logout_button(logged_in):
    assert 'action="/logout"' in logged_in.get("/roster").text


# TC-01: preview shows 104 rows; remove the 2 staff rows; confirm; 102 active entries.
def test_upload_preview_then_confirm_saves_102(logged_in):
    preview = upload(logged_in, "roster.csv")
    assert preview.status_code == 200
    assert "104" in preview.text
    assert "student001@example.com" in preview.text
    # Nothing is saved before the lecturer confirms.
    assert active_count(logged_in) == 0

    rows = sample_rows()
    keep = [i for i, r in enumerate(rows) if r['דוא"ל'].startswith("student")]
    assert len(keep) == 102
    form = {
        "first_name": [r["שם פרטי"] for r in rows],
        "last_name": [r["שם משפחה"] for r in rows],
        "email": [r['דוא"ל'] for r in rows],
        "keep": [str(i) for i in keep],
    }
    reply = logged_in.post("/roster/confirm", data=form)
    assert reply.status_code == 303
    assert active_count(logged_in) == 102
    assert "102" in logged_in.get(reply.headers["location"]).text


# TC-02: a bad file shows the problem and saves nothing.
def test_bad_file_names_the_missing_column(logged_in):
    reply = upload(logged_in, "roster_bad.csv")
    assert reply.status_code == 400
    assert 'דוא"ל' in html.unescape(reply.text)
    assert active_count(logged_in) == 0


# TC-03: duplicate emails are listed and nothing is saved.
def test_duplicate_file_lists_the_emails(logged_in):
    reply = upload(logged_in, "roster_duplicates.csv")
    assert reply.status_code == 400
    assert "student001@example.com" in reply.text
    assert active_count(logged_in) == 0


# The confirm form comes from a browser, so it is checked again on the server.
def test_confirm_with_duplicate_rows_saves_nothing(logged_in):
    form = {
        "first_name": ["א", "ב"], "last_name": ["ג", "ד"],
        "email": ["a@example.com", "a@example.com"], "keep": ["0", "1"],
    }
    assert logged_in.post("/roster/confirm", data=form).status_code == 400
    assert active_count(logged_in) == 0


# Removing every row would empty the roster, so it is refused.
def test_confirm_with_no_rows_kept_is_refused(logged_in):
    form = {"first_name": ["א"], "last_name": ["ב"], "email": ["a@example.com"]}
    assert logged_in.post("/roster/confirm", data=form).status_code == 400
    assert active_count(logged_in) == 0


# A name with HTML in it must be shown as text, never run.
def test_names_are_escaped_in_the_preview(logged_in):
    data = 'שם פרטי,שם משפחה,"דוא""ל"\n<b>x</b>,y,a@example.com\n'.encode("utf-8")
    reply = logged_in.post("/roster/upload", files={"file": ("r.csv", data, "text/csv")})
    assert "<b>x</b>" not in reply.text
    assert "&lt;b&gt;x&lt;/b&gt;" in reply.text


def test_home_goes_to_the_class_page(client):
    reply = client.get("/")
    assert reply.status_code == 303 and reply.headers["location"] == "/class"
