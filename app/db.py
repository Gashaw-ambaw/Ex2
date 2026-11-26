"""The database: creates the SQLite tables and opens connections."""
import logging
import os
import sqlite3
from contextlib import closing

# uvicorn shows this logger, so the line is visible in the Railway deploy log.
log = logging.getLogger("uvicorn.error")

# The 15 tables of EDD section 3. Column types and checks are a proposal; the EDD lists fields only.
TABLES = (
    "roster_entries", "devices", "class_sessions", "marks", "flags",
    "class_location", "head_counts", "comments", "polls", "poll_answers",
    "summaries", "jobs", "repo_results", "f5_reports", "checklist",
)

# "IF NOT EXISTS" means running this again does nothing, so it is safe at every start.
# Times are text in UTC. CHECK lines stop wrong values. UNIQUE lines stop double rows.
SCHEMA = """
-- Students from the Moodle file. active = 0 means "not in the newest file", kept for old marks.
CREATE TABLE IF NOT EXISTS roster_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    active INTEGER NOT NULL DEFAULT 1,
    source TEXT NOT NULL DEFAULT 'upload' CHECK (source IN ('upload', 'manual')),
    created_at TEXT NOT NULL
);
-- One row per registered browser. id is the random value in the device cookie.
CREATE TABLE IF NOT EXISTS devices (
    id TEXT PRIMARY KEY,
    roster_id INTEGER NOT NULL REFERENCES roster_entries(id),
    created_at TEXT NOT NULL
);
-- One row per class (date is the Israel date). The window_* columns hold the attendance window.
CREATE TABLE IF NOT EXISTS class_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    name TEXT,
    window_opened_at TEXT,
    window_ends_at TEXT,
    window_closed_at TEXT
);
-- One row per attendance mark. device_id is empty when the lecturer adds the mark by hand.
-- UNIQUE(session_id, roster_id): a student is marked once per class.
-- UNIQUE(session_id, device_id): a device marks one student per class (empty values do not clash).
CREATE TABLE IF NOT EXISTS marks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES class_sessions(id),
    roster_id INTEGER NOT NULL REFERENCES roster_entries(id),
    device_id TEXT REFERENCES devices(id),
    marked_at TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('self', 'manual')),
    status TEXT NOT NULL DEFAULT 'normal' CHECK (status IN ('normal', 'unverified')),
    location_ok INTEGER CHECK (location_ok IN (0, 1)),
    UNIQUE (session_id, roster_id),
    UNIQUE (session_id, device_id)
);
-- Warnings for the lecturer (new device, device reuse, ...). They never block or punish anyone.
CREATE TABLE IF NOT EXISTS flags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES class_sessions(id),
    roster_id INTEGER,
    device_id TEXT,
    kind TEXT NOT NULL CHECK (kind IN ('new_device', 'relinked', 'device_reuse', 'location')),
    created_at TEXT NOT NULL
);
-- The room location set by the lecturer. CHECK (id = 1) allows only one row.
CREATE TABLE IF NOT EXISTS class_location (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    updated_at TEXT NOT NULL
);
-- The people count from the class photo and the gap to the marks.
CREATE TABLE IF NOT EXISTS head_counts (
    session_id INTEGER PRIMARY KEY REFERENCES class_sessions(id),
    count INTEGER NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('auto', 'manual')),
    marks_at_count INTEGER NOT NULL,
    gap INTEGER NOT NULL,
    alert INTEGER NOT NULL CHECK (alert IN (0, 1)),
    created_at TEXT NOT NULL
);
-- F2: anonymous comments. anon_id is a random browser id, not a student.
CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES class_sessions(id),
    anon_id TEXT NOT NULL,
    text TEXT NOT NULL,
    hidden INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS polls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES class_sessions(id),
    question TEXT NOT NULL,
    options_json TEXT NOT NULL,
    correct_index INTEGER,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
    created_at TEXT NOT NULL,
    closed_at TEXT
);
-- F3: polls. This index allows only one open poll at a time.
CREATE UNIQUE INDEX IF NOT EXISTS one_open_poll ON polls(status) WHERE status = 'open';
-- One answer per browser per poll (the primary key).
CREATE TABLE IF NOT EXISTS poll_answers (
    poll_id INTEGER NOT NULL REFERENCES polls(id),
    anon_id TEXT NOT NULL,
    option_index INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (poll_id, anon_id)
);
-- F4: lecture summaries.
CREATE TABLE IF NOT EXISTS summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES class_sessions(id),
    text TEXT NOT NULL,
    created_at TEXT NOT NULL
);
-- Background jobs (F4 summary, F5 class review). boot_id tells which server run started the job.
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL CHECK (kind IN ('summary', 'class_review')),
    status TEXT NOT NULL CHECK (status IN ('running', 'done', 'failed')),
    progress INTEGER NOT NULL DEFAULT 0,
    total INTEGER NOT NULL DEFAULT 0,
    boot_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    finished_at TEXT,
    error TEXT
);
-- This index allows only one running job of each kind.
CREATE UNIQUE INDEX IF NOT EXISTS one_running_job ON jobs(kind) WHERE status = 'running';
-- F5: one row per reviewed repo. No emails are stored.
CREATE TABLE IF NOT EXISTS repo_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES jobs(id),
    repo_url TEXT NOT NULL,
    accessible INTEGER NOT NULL,
    layer1_json TEXT,
    ratings_json TEXT,
    flags TEXT,
    created_at TEXT NOT NULL
);
-- F5: one row per student report, used only for the per-browser delay and the daily cap.
CREATE TABLE IF NOT EXISTS f5_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    anon_id TEXT NOT NULL,
    created_at TEXT NOT NULL
);
-- F5: the review checklist text. One row only.
CREATE TABLE IF NOT EXISTS checklist (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    text TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


class Db:
    """One sqlite3 connection per call. The caller closes it."""

    def __init__(self, path):
        self.path = str(path)

    def connect(self):
        # timeout=5: wait up to 5 seconds if another request is writing.
        conn = sqlite3.connect(self.path, timeout=5)
        # Rows can be read by column name, for example row["email"].
        conn.row_factory = sqlite3.Row
        # SQLite ignores foreign keys unless this is switched on for each connection.
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def create_tables(self):
        # Make the folder (for example /data) if it does not exist yet.
        folder = os.path.dirname(self.path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        # "with conn" saves the changes (commit); closing() closes the connection.
        with closing(self.connect()) as conn, conn:
            conn.executescript(SCHEMA)
            # Count the tables, so the log line below proves the database is ready.
            count = conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            ).fetchone()[0]
        log.info("Db ready: %d tables at %s", count, self.path)
