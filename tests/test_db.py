"""Tests of the database: the tables are created and the schema rules refuse wrong rows."""
import sqlite3

import pytest

from app.db import TABLES, Db


# Helpers: a fresh database with all tables, and short ways to add test rows.
@pytest.fixture
def db(tmp_path):
    db = Db(tmp_path / "test.db")
    db.create_tables()
    return db


def _table_names(db):
    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    finally:
        conn.close()
    return {r["name"] for r in rows}


def _insert_session(conn):
    return conn.execute("INSERT INTO class_sessions (date) VALUES ('2026-11-24')").lastrowid


def _insert_student(conn, n):
    return conn.execute(
        "INSERT INTO roster_entries (first_name, last_name, email, created_at) VALUES (?, ?, ?, 't')",
        (f"F{n}", f"L{n}", f"s{n}@example.com"),
    ).lastrowid


# Each test below checks one rule of the schema. IntegrityError means the database refused the row.
def test_creates_the_15_tables_of_the_edd(db):
    assert len(TABLES) == 15
    assert _table_names(db) == set(TABLES)


def test_create_tables_twice_is_safe(db):
    db.create_tables()
    assert _table_names(db) == set(TABLES)


def test_creates_the_parent_folder(tmp_path):
    db = Db(tmp_path / "new_folder" / "test.db")
    db.create_tables()
    assert (tmp_path / "new_folder" / "test.db").is_file()


def test_foreign_keys_are_on(db):
    conn = db.connect()
    try:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO devices (id, roster_id, created_at) VALUES ('d', 999, 't')")
    finally:
        conn.close()


def test_one_mark_per_student_per_session(db):
    conn = db.connect()
    try:
        session, student = _insert_session(conn), _insert_student(conn, 1)
        sql = "INSERT INTO marks (session_id, roster_id, marked_at, source) VALUES (?, ?, 't', 'manual')"
        conn.execute(sql, (session, student))
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(sql, (session, student))
    finally:
        conn.close()


def test_one_student_per_device_per_session_but_manual_marks_have_no_device(db):
    conn = db.connect()
    try:
        session = _insert_session(conn)
        a, b, c = (_insert_student(conn, n) for n in (1, 2, 3))
        conn.execute("INSERT INTO devices (id, roster_id, created_at) VALUES ('d1', ?, 't')", (a,))
        sql = (
            "INSERT INTO marks (session_id, roster_id, device_id, marked_at, source) "
            "VALUES (?, ?, ?, 't', ?)"
        )
        conn.execute(sql, (session, a, "d1", "self"))
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(sql, (session, b, "d1", "self"))
        # Manual marks have no device, so several can exist in one session.
        conn.execute(sql, (session, b, None, "manual"))
        conn.execute(sql, (session, c, None, "manual"))
    finally:
        conn.close()


def test_one_running_job_per_kind(db):
    conn = db.connect()
    try:
        sql = "INSERT INTO jobs (kind, status, boot_id, created_at) VALUES (?, ?, 'boot', 't')"
        conn.execute(sql, ("summary", "running"))
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(sql, ("summary", "running"))
        conn.execute(sql, ("class_review", "running"))
        conn.execute(sql, ("summary", "done"))
    finally:
        conn.close()


def test_one_open_poll(db):
    conn = db.connect()
    try:
        session = _insert_session(conn)
        sql = (
            "INSERT INTO polls (session_id, question, options_json, status, created_at) "
            "VALUES (?, 'q', '[]', ?, 't')"
        )
        conn.execute(sql, (session, "open"))
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(sql, (session, "open"))
        conn.execute(sql, (session, "closed"))
    finally:
        conn.close()


def test_class_location_and_checklist_hold_one_row(db):
    conn = db.connect()
    try:
        conn.execute("INSERT INTO class_location (id, lat, lon, updated_at) VALUES (1, 1.0, 2.0, 't')")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO class_location (id, lat, lon, updated_at) VALUES (2, 1.0, 2.0, 't')")
        conn.execute("INSERT INTO checklist (id, text, updated_at) VALUES (1, 'x', 't')")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO checklist (id, text, updated_at) VALUES (2, 'x', 't')")
    finally:
        conn.close()
