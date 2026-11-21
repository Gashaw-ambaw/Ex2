import os
import sqlite3
import threading
import time
import urllib.request
from contextlib import closing
import secrets
from datetime import datetime, timezone
from html import escape

from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

# Settings and secrets come from environment variables only, never from the code.
GOOGLE_CLIENT_ID = os.environ["GOOGLE_CLIENT_ID"]
GOOGLE_CLIENT_SECRET = os.environ["GOOGLE_CLIENT_SECRET"]
SECRET_KEY = os.environ["SECRET_KEY"]
BASE_URL = os.environ["BASE_URL"].rstrip("/")
# Google sends the user back to this address after sign-in.
REDIRECT_URI = f"{BASE_URL}/auth/callback"


# SQLite file. On Railway it must be inside the Volume (DB_PATH=/data/s1.db).
DB_PATH = os.environ["DB_PATH"]
# A random id for each server run. After a restart it changes; old rows keep the old id.
BOOT_ID = secrets.token_hex(4)

app = FastAPI()

# Sessions: the logged-in user is kept in a signed cookie (the signature uses SECRET_KEY).
# https_only: the browser sends this cookie only over HTTPS. Lasts 24 hours.
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    https_only=True,
    same_site="lax",
    max_age=86400,
)

# Google sign-in (OpenID Connect). The metadata URL tells the library Google's addresses.
oauth = OAuth()
oauth.register(
    name="google",
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


# Hello page. The server time shows that the page is live and not from the browser cache.
@app.get("/", response_class=HTMLResponse)
def hello():
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return f"""<!doctype html>
<html><head><meta name="viewport" content="width=device-width, initial-scale=1">
<title>S1 Hello</title></head>
<body><h1>Hello from S1</h1><p>Server time (UTC): {now}</p></body></html>"""


# Simple check that the server is running.
@app.get("/health")
def health():
    return {"status": "ok"}


# Small HTML page for the cookie test.
def _cookie_page(body: str) -> str:
    return f"""<!doctype html>
<html><head><meta name="viewport" content="width=device-width, initial-scale=1">
<title>S1 Cookie</title></head>
<body><h1>S1 cookie test</h1><p>{body}</p>
<p><a href="/cookie">Reload this page</a></p></body></html>"""


# Cookie test: the first visit sets a cookie, a reload shows the browser sent it back.
@app.get("/cookie", response_class=HTMLResponse)
def cookie_test(request: Request):
    value = request.cookies.get("s1_cookie")
    if value:
        # The cookie came back, so cookies work in this browser.
        return HTMLResponse(_cookie_page(f"Cookie found: {value}. The browser sent it back."))
    # First visit: make a random value and set it as a cookie.
    value = secrets.token_hex(4)
    response = HTMLResponse(_cookie_page(f"No cookie yet. I set one now: {value}. Reload to check."))
    response.set_cookie("s1_cookie", value, max_age=86400, httponly=True, secure=True, samesite="lax")
    return response


# Generic HTML page. escape() makes text safe to show (no HTML injection).
def _page(title: str, body_html: str) -> str:
    return f"""<!doctype html>
<html><head><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title></head>
<body><h1>{escape(title)}</h1>{body_html}</body></html>"""


# Step 1 of sign-in: send the user to Google.
@app.get("/login")
async def login(request: Request):
    return await oauth.google.authorize_redirect(request, REDIRECT_URI)


# Step 2 of sign-in: Google sends the user back here with a code.
@app.get("/auth/callback")
async def auth_callback(request: Request):
    try:
        # Exchange the code for the user's details.
        token = await oauth.google.authorize_access_token(request)
    except OAuthError as error:
        # Sign-in failed or was cancelled: show a short error.
        message = escape(str(error.error))
        return HTMLResponse(
            _page("Login failed", f"<p>Google returned an error: {message}</p>"),
            status_code=400,
        )
    info = token.get("userinfo") or {}
    # Keep only what we need in the session.
    request.session["user"] = {
        "email": info.get("email"),
        "name": info.get("name"),
        "email_verified": info.get("email_verified"),
    }
    return RedirectResponse("/me")


# Shows who is signed in, or a sign-in link if nobody is.
@app.get("/me", response_class=HTMLResponse)
def me(request: Request):
    user = request.session.get("user")
    if not user:
        return _page("Not signed in", '<p><a href="/login">Sign in with Google</a></p>')
    body = (
        f"<p>Email: {escape(str(user.get('email')))}</p>"
        f"<p>Name: {escape(str(user.get('name')))}</p>"
        f"<p>Email verified: {escape(str(user.get('email_verified')))}</p>"
        '<p><a href="/logout">Sign out</a></p>'
    )
    return _page("Signed in", body)


# Sign out: clear the session.
@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/me")



# ----- S1 step 6: SQLite write and restart test (temporary, delete after S1) -----
def _db():
    # Open the file and create the table if it does not exist yet.
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS s1_rows ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "created_at TEXT NOT NULL, "
        "boot_id TEXT NOT NULL)"
    )
    return conn


def _db_error_page(error: Exception) -> HTMLResponse:
    return HTMLResponse(
        _page("DB error", f"<p>{escape(str(error))}</p>"), status_code=500
    )


# Shows where the file is and whether the folder is a mounted Volume.
@app.get("/db/info", response_class=HTMLResponse)
def db_info():
    folder = os.path.dirname(DB_PATH) or "."
    lines = [
        f"DB_PATH: {DB_PATH}",
        f"Folder exists: {os.path.isdir(folder)}",
        f"Folder is a mount point (Volume): {os.path.ismount(folder)}",
        f"File exists: {os.path.isfile(DB_PATH)}",
        f"File size (bytes): {os.path.getsize(DB_PATH) if os.path.isfile(DB_PATH) else '-'}",
        f"This server run (boot id): {BOOT_ID}",
    ]
    try:
        with closing(_db()) as conn:
            count = conn.execute("SELECT COUNT(*) FROM s1_rows").fetchone()[0]
        lines.append(f"Rows in table: {count}")
    except sqlite3.Error as error:
        return _db_error_page(error)
    return _page("DB info", "".join(f"<p>{escape(line)}</p>" for line in lines))


# Adds one row (time + boot id), then shows the list.
@app.get("/db/write")
def db_write():
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        with closing(_db()) as conn, conn:
            conn.execute(
                "INSERT INTO s1_rows (created_at, boot_id) VALUES (?, ?)",
                (now, BOOT_ID),
            )
    except sqlite3.Error as error:
        return _db_error_page(error)
    return RedirectResponse("/db/list")


# Shows all rows.
@app.get("/db/list", response_class=HTMLResponse)
def db_list():
    try:
        with closing(_db()) as conn:
            rows = conn.execute(
                "SELECT id, created_at, boot_id FROM s1_rows ORDER BY id"
            ).fetchall()
    except sqlite3.Error as error:
        return _db_error_page(error)
    items = "".join(
        f"<li>#{r[0]} | {escape(r[1])} | boot {escape(r[2])}</li>" for r in rows
    )
    body = (
        f"<p>This server run (boot id): {escape(BOOT_ID)}</p>"
        f"<p>Rows: {len(rows)}</p><ul>{items}</ul>"
        '<p><a href="/db/write">Add a row</a> | <a href="/db/info">Info</a></p>'
    )
    return _page("DB rows", body)


# ----- S1 step 7: background job test (temporary, delete after S1) -----
# Step time in seconds. Default 10 (9 steps = about 90 s). Tests set it lower.
JOB_STEP_SEC = float(os.environ.get("JOB_STEP_SEC", "10"))
JOB_STEPS = 9
# One outbound HTTPS call at the end of the job (checks that the host can reach the internet).
JOB_URL = "https://accounts.google.com/.well-known/openid-configuration"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _jobs_db():
    # Open the DB and create the jobs table if it does not exist yet.
    conn = _db()
    conn.execute(
        "CREATE TABLE IF NOT EXISTS s1_jobs ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "status TEXT NOT NULL, "
        "progress INTEGER NOT NULL, "
        "boot_id TEXT NOT NULL, "
        "created_at TEXT NOT NULL, "
        "finished_at TEXT, "
        "error TEXT)"
    )
    # At most one job can have the status "running" (stops a double start).
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS s1_one_running "
        "ON s1_jobs(status) WHERE status = 'running'"
    )
    return conn


def _fail_dead_jobs(conn):
    # A "running" job from another boot id belongs to a dead process: mark it failed.
    conn.execute(
        "UPDATE s1_jobs SET status = 'failed', error = 'server restarted', finished_at = ? "
        "WHERE status = 'running' AND boot_id != ?",
        (_now(), BOOT_ID),
    )


def _job_update(job_id, progress=None, status="running", error=None):
    # Used by the job thread, with its own connection. Only a running job can change.
    finished = None if status == "running" else _now()
    with closing(_jobs_db()) as conn, conn:
        conn.execute(
            "UPDATE s1_jobs SET progress = COALESCE(?, progress), status = ?, "
            "error = ?, finished_at = ? WHERE id = ? AND status = 'running'",
            (progress, status, error, finished, job_id),
        )


def _run_job(job_id):
    # The job: 9 slow steps, then one outbound HTTPS request.
    try:
        for step in range(1, JOB_STEPS + 1):
            time.sleep(JOB_STEP_SEC)
            _job_update(job_id, progress=step)
        with urllib.request.urlopen(JOB_URL, timeout=10) as reply:
            if reply.status != 200:
                raise RuntimeError(f"HTTP {reply.status}")
        _job_update(job_id, status="done")
    except Exception as error:
        # Any problem: keep the progress, save a short error text.
        _job_update(job_id, status="failed", error=str(error)[:200])


# Creates a job row and starts the thread. Returns at once, then shows the status page.
@app.get("/job/start")
def job_start():
    try:
        with closing(_jobs_db()) as conn, conn:
            _fail_dead_jobs(conn)
            cursor = conn.execute(
                "INSERT INTO s1_jobs (status, progress, boot_id, created_at) "
                "VALUES ('running', 0, ?, ?)",
                (BOOT_ID, _now()),
            )
            job_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        # A job is already running: do not start a second one.
        return RedirectResponse("/job/status")
    except sqlite3.Error as error:
        return _db_error_page(error)
    threading.Thread(target=_run_job, args=(job_id,), daemon=True).start()
    return RedirectResponse("/job/status")


# Shows the latest job. Reloads itself every 5 seconds while the job is running.
@app.get("/job/status", response_class=HTMLResponse)
def job_status():
    try:
        with closing(_jobs_db()) as conn, conn:
            _fail_dead_jobs(conn)
            row = conn.execute(
                "SELECT id, status, progress, boot_id, created_at, finished_at, error "
                "FROM s1_jobs ORDER BY id DESC LIMIT 1"
            ).fetchone()
    except sqlite3.Error as error:
        return _db_error_page(error)
    if row is None:
        return _page("Job status", '<p>No job yet.</p><p><a href="/job/start">Start a job</a></p>')
    job_id, status, progress, boot_id, created_at, finished_at, error = row
    lines = [
        f"Job: #{job_id}",
        f"Status: {status}",
        f"Progress: {progress} / {JOB_STEPS}",
        f"Started: {created_at}",
        f"Finished: {finished_at or '-'}",
        f"Job run (boot id): {boot_id}",
        f"This server run (boot id): {BOOT_ID}",
    ]
    if error:
        lines.append(f"Error: {error}")
    body = "".join(f"<p>{escape(line)}</p>" for line in lines)
    body += '<p><a href="/job/status">Refresh now</a> | <a href="/job/start">Start a job</a></p>'
    page = _page("Job status", body)
    if status == "running":
        page = page.replace("</head>", '<meta http-equiv="refresh" content="5"></head>')
    return page

