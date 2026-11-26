from contextlib import closing
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

NOON = datetime(2026, 11, 24, 12, 0, 0, tzinfo=timezone.utc)
DANA = {"first_name": "Dana", "last_name": "Levi", "email": "dana@example.com"}
RON = {"first_name": "Ron", "last_name": "Cohen", "email": "ron@example.com"}
AVI = {"first_name": "Avi", "last_name": "Mor", "email": "avi@example.com"}


@pytest.fixture
def app(settings):
    app = create_app(settings)
    app.state.clock.set(NOON)
    app.state.roster.save([DANA, RON, AVI])
    return app


@pytest.fixture
def client(app):
    return TestClient(app, base_url="https://testserver", follow_redirects=False)


@pytest.fixture
def lecturer(client):
    assert client.post("/login", data={"password": "test-password"}).status_code == 303
    return client


def entry_id(app, person):
    return app.state.roster.find_by_email(person["email"])["id"]


def marked_class(app):
    """Dana has a mark without flags, Ron a mark with a flag, Avi only a flag."""
    attendance = app.state.attendance
    session = attendance.start_class()["id"]
    attendance.add_manual(session, entry_id(app, DANA))
    attendance.add_manual(session, entry_id(app, RON))
    attendance.add_flags(session, entry_id(app, RON), "dev-ron", ["location"])
    attendance.add_flags(session, entry_id(app, AVI), "dev-ron", ["device_reuse"])
    return session


def marks(app):
    with closing(app.state.db.connect()) as conn:
        return [tuple(r) for r in conn.execute("SELECT roster_id, source, status FROM marks ORDER BY id")]


def mark_id(app, person):
    with closing(app.state.db.connect()) as conn:
        return conn.execute("SELECT id FROM marks WHERE roster_id = ?", (entry_id(app, person),)).fetchone()[0]


def table_part(text):
    return text.split("<table>")[1].split("</table>")[0]


# TC-42: the review pages need the password.
@pytest.mark.parametrize("path", ["status", "reset", "add", "export"])
def test_review_actions_need_login_tc42(client, path):
    reply = client.post(f"/class/review/{path}")
    assert reply.status_code == 303 and reply.headers["location"] == "/login"


def test_review_page_needs_login_tc42(client):
    reply = client.get("/class/review")
    assert reply.status_code == 303 and reply.headers["location"] == "/login"


def test_review_without_a_class(lecturer):
    reply = lecturer.get("/class/review")
    assert reply.status_code == 200 and "No class yet." in reply.text
    assert 'href="/class/review"' in reply.text  # the nav link


def test_flagged_row_comes_first_and_is_highlighted_tc33(app, lecturer):
    marked_class(app)
    table = table_part(lecturer.get("/class/review").text)
    assert table.index("Ron Cohen") < table.index("Dana Levi")
    assert table.count('class="flagged"') == 1 and "location" in table


def test_flags_without_a_mark_are_one_line(app, lecturer):
    marked_class(app)
    text = lecturer.get("/class/review").text
    assert "Flags without a mark:" in text and "Avi Mor (device_reuse)" in text
    assert "Avi Mor" not in table_part(text)


def test_review_shows_a_class_of_an_earlier_day(app, lecturer):
    marked_class(app)
    app.state.clock.set(NOON + timedelta(days=1))
    text = lecturer.get("/class/review").text
    assert "Class of 2026-11-24" in text and "Dana Levi" in text


def test_unverified_and_back_tc33_tc34(app, lecturer):
    marked_class(app)
    data = {"mark_id": mark_id(app, DANA), "status": "unverified"}
    reply = lecturer.post("/class/review/status", data=data)
    assert reply.status_code == 303 and reply.headers["location"] == "/class/review"
    assert marks(app)[0][2] == "unverified"
    lecturer.post("/class/review/status", data={**data, "status": "normal"})
    assert marks(app)[0][2] == "normal"


def test_reset_removes_the_row_tc39(app, lecturer):
    marked_class(app)
    reply = lecturer.post("/class/review/reset", data={"mark_id": mark_id(app, DANA)})
    assert reply.status_code == 303
    assert [row[0] for row in marks(app)] == [entry_id(app, RON)]
    assert "Dana Levi" not in table_part(lecturer.get("/class/review").text)


def test_add_a_mark_by_hand_tc35(app, lecturer):
    marked_class(app)
    reply = lecturer.post("/class/review/add", data={"roster_id": entry_id(app, AVI)})
    assert reply.status_code == 303
    assert marks(app)[-1] == (entry_id(app, AVI), "manual", "normal")


def test_add_a_marked_student_says_so_tc37(app, lecturer):
    marked_class(app)
    reply = lecturer.post("/class/review/add", data={"roster_id": entry_id(app, DANA)})
    assert reply.status_code == 400 and "Already marked at 14:00." in reply.text
    assert len(marks(app)) == 2


def test_add_a_student_who_is_not_on_the_roster_tc36(app, lecturer):
    marked_class(app)
    new = {"first_name": "Noa", "last_name": "Bar", "email": "noa@example.com"}
    assert lecturer.post("/roster/add", data=new).status_code == 303
    assert "Noa Bar (noa@example.com)" in lecturer.get("/class/review").text  # now in the picker, first name first
    lecturer.post("/class/review/add", data={"roster_id": entry_id(app, new)})
    assert marks(app)[-1] == (entry_id(app, new), "manual", "normal")


def test_export_downloads_a_csv_tc40(app, lecturer):
    marked_class(app)
    reply = lecturer.post("/class/review/export")
    assert reply.status_code == 200
    assert reply.headers["content-type"].startswith("text/csv")
    assert 'filename="attendance_2026-11-24.csv"' in reply.headers["content-disposition"]
    lines = reply.content.decode("utf-8-sig").splitlines()
    assert reply.content.startswith(b"\xef\xbb\xbf")
    assert lines[0] == "name,email,time,source,status,flags" and len(lines) == 3


def test_export_error_keeps_the_table_tc41(app, lecturer, monkeypatch):
    marked_class(app)

    def broken(session_id):
        raise OSError("forced")

    monkeypatch.setattr(app.state.attendance, "export_csv", broken)
    reply = lecturer.post("/class/review/export")
    assert reply.status_code == 500 and "Export failed. Try again." in reply.text
    assert "Dana Levi" in table_part(reply.text) and len(marks(app)) == 2
