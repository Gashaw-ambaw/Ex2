"""Tests of the Check page (students, no sign-in) and the Repos page (lecturer) with fake GitHub and model."""
from contextlib import closing

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.test_repos import HEADER, LINK, NOON, FakeGitHub, FakeLlm, csv_row, make_csv

REFRESH = '<meta http-equiv="refresh" content="20">'
CHECK_LINK = '<form method="get" action="/check"><button type="submit">Check my repo</button></form>'


class Spawn:
    hold = False

    def __call__(self, work):
        if not self.hold:
            work()


@pytest.fixture
def github():
    return FakeGitHub()


@pytest.fixture
def llm():
    return FakeLlm()


@pytest.fixture
def spawn():
    return Spawn()


@pytest.fixture
def app(settings, llm, github, spawn):
    app = create_app(settings, llm=llm, github=github, spawn=spawn)
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


def check(client, url=LINK):
    return client.post("/check", data={"url": url})


def upload(client, data, name="list.csv"):
    return client.post("/repos/upload", files={"file": (name, data, "text/csv")})


def count(app, table):
    with closing(app.state.db.connect()) as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


# TC-90: no sign-in; the cookie is the anonymous one (FR-18).
def test_check_page_tc90(student):
    reply = student.get("/check")
    assert reply.status_code == 200
    assert "Check my repo" in reply.text and 'action="/check"' in reply.text
    assert "anon" in reply.cookies and "/logout" not in reply.text


# TC-90: the report marks what code checked and what a model wrote (UC-11 s6).
def test_report_tc90(app, student, llm):
    student.get("/check")
    llm.reply = "Remark <one>.\nTwo.\nThree."
    reply = check(student)
    assert reply.status_code == 200
    page = reply.text
    for text in (
        "Report: some-user/repo-a", "Checked by code: files", "Checked by code: links in the README",
        "Written by a model, may be wrong", "Remark &lt;one&gt;.",
        "Problem and scope (README.md): ok, 3.9 KB, expected 3-5 KB.",
        "SRS (SRS.md): too short, 2.0 KB, expected 3-5 KB.",
        "Algorithm description (algorithm.md): missing, expected 3-5 KB.",
        "docs/SRS.md: ok", "No class comparison yet.",
    ):
        assert text in page, text
    assert count(app, "f5_reports") == 1 and count(app, "repo_results") == 0


def test_report_with_class_counts_tc89(app, student, lecturer):
    app.state.repos.start_class_review([LINK])
    page = check(student).text
    assert "Class: 1 ok (1 repo)." in page and "No class comparison yet." not in page


@pytest.mark.parametrize("url, text", [
    ("https://gitlab.com/a/b", "The link is not valid. Use: https://github.com/owner/repo"),
    ("", "The link is not valid."),
], ids=["gitlab", "empty"])
def test_bad_link_page_tc83(student, url, text):
    reply = check(student, url)
    assert reply.status_code == 400 and text in reply.text


def test_wait_page_tc84(student):
    student.get("/check")
    check(student)
    reply = check(student)
    assert reply.status_code == 400 and "Wait a moment" in reply.text and LINK in reply.text


def test_private_and_limit_pages_tc85(app, student, github):
    page = check(student, "https://github.com/u/secret").text
    assert "The repo is private or not found." in page and "Checked by code" not in page
    app.state.clock.set(NOON.replace(minute=5))
    github.limited.add("some-user/repo-a")
    reply = check(student)
    assert reply.status_code == 400 and "Try again in about an hour." in reply.text


def test_model_off_page_tc88(student, llm):
    llm.error = RuntimeError("down")
    page = check(student).text
    assert "Model check not available." in page and "Checked by code: files" in page


# TC-94: the lecturer pages need the password.
def test_needs_login_tc94(app, student):
    replies = [
        student.get("/repos"),
        student.post("/repos/checklist", data={"checklist": "A: a.md | 1-2"}),
        upload(student, make_csv([csv_row(LINK)])),
        student.post("/repos/run", data={"link": LINK}),
    ]
    for reply in replies:
        assert reply.status_code == 303 and reply.headers["location"] == "/login"
    assert count(app, "jobs") == 0 and count(app, "checklist") == 0


def test_page_and_menu_tc94(lecturer):
    page = lecturer.get("/repos").text
    assert '<a href="/repos">Repos</a>' in page and "SRS: SRS.md | 3-5" in page
    assert "No class review yet." in page and REFRESH not in page


def test_checklist_page_tc91(lecturer):
    reply = lecturer.post("/repos/checklist", data={"checklist": "Design: design.md | 1-2"})
    assert reply.status_code == 303 and reply.headers["location"] == "/repos?saved=1"
    page = lecturer.get(reply.headers["location"]).text
    assert "Saved." in page and "Design: design.md | 1-2" in page
    reply = lecturer.post("/repos/checklist", data={"checklist": "wrong line"})
    assert reply.status_code == 400 and "Line 1 is not valid." in reply.text and "wrong line" in reply.text
    assert "Design: design.md | 1-2" in lecturer.get("/repos").text


# TC-92 through the page: count first, nothing stored; names and emails never shown.
def test_upload_preview_tc92(app, lecturer):
    data = make_csv([csv_row(LINK), csv_row("https://gitlab.com/u/c"), csv_row(LINK)])
    page = upload(lecturer, data).text
    assert "1 link, 1 invalid." in page and "https://gitlab.com/u/c" in page
    assert f'<input type="hidden" name="link" value="{LINK}">' in page and "Run review" in page
    assert "example.com" not in page and count(app, "jobs") == 0 and count(app, "repo_results") == 0


def test_upload_errors_tc92(app, lecturer):
    for data, text in [
        (b"\xff\xfe\x00", "The file must be a CSV file of at most 1 MB."),
        (make_csv([], HEADER), "No GitHub link column found."),
    ]:
        reply = upload(lecturer, data)
        assert reply.status_code == 400 and text in reply.text
    reply = lecturer.post("/repos/upload")
    assert reply.status_code == 400 and "Choose a CSV file." in reply.text
    assert count(app, "jobs") == 0


# TC-94: run, table with statuses, counts row and remarks.
def test_run_and_table_tc94(lecturer, llm):
    llm.reply = "Remark <one>.\nTwo.\nThree."
    reply = lecturer.post("/repos/run", data={"link": [LINK, "https://github.com/u/secret"]})
    assert reply.status_code == 303 and reply.headers["location"] == "/repos"
    page = lecturer.get("/repos").text
    for text in ("some-user/repo-a", "u/secret", "private or not found", "too short", "missing",
                 "Remark &lt;one&gt;.", "1 ok (1 repo)", "Written by a model, may be wrong"):
        assert text in page, text
    assert REFRESH not in page


def test_running_page_tc94(app, lecturer, spawn):
    spawn.hold = True
    lecturer.post("/repos/run", data={"link": LINK})
    page = lecturer.get("/repos").text
    assert "Reviewing: 0 of 0." in page and REFRESH in page and 'action="/repos/upload"' not in page
    reply = lecturer.post("/repos/run", data={"link": LINK})
    assert reply.status_code == 400 and "A class review is already running." in reply.text


def test_failed_run_tc94(app, lecturer, github):
    def broken(repo):
        raise RuntimeError("secret detail")

    github.tree = broken
    lecturer.post("/repos/run", data={"link": LINK})
    page = lecturer.get("/repos").text
    assert "Failed: run again." in page and "secret detail" not in page


def test_run_without_links_tc94(lecturer):
    reply = lecturer.post("/repos/run")
    assert reply.status_code == 400 and "No links. Upload the file again." in reply.text


# TC-94: /c shows the button, with and without a class.
def test_class_page_button_tc94(app, student):
    assert CHECK_LINK in student.get("/c").text
    app.state.attendance.start_class()
    assert CHECK_LINK in student.get("/c").text
