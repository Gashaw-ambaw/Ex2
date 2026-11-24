from contextlib import closing
from pathlib import Path

import pytest

from app.roster import RosterService

SAMPLES = Path(__file__).parent.parent / "sample_data"
HEADER = 'שם פרטי,שם משפחה,"דוא""ל",קבוצות\n'


def csv_bytes(*rows):
    # Builds a small roster file in memory. Each row is "first,last,email,group".
    return (HEADER + "\n".join(rows) + "\n").encode("utf-8")


@pytest.fixture
def roster(db, clock):
    return RosterService(db, clock)


def entries(db):
    # All roster rows as a dict: email -> (first_name, last_name, active).
    with closing(db.connect()) as conn:
        rows = conn.execute("SELECT * FROM roster_entries").fetchall()
    return {r["email"]: (r["first_name"], r["last_name"], r["active"]) for r in rows}


# TC-01 (service part): the sample file has 104 rows; only first name, last name, email are read.
def test_sample_file_gives_104_rows_with_three_fields(roster):
    preview = roster.parse_upload((SAMPLES / "roster.csv").read_bytes())
    assert preview.errors == []
    assert len(preview.rows) == 104
    assert set(preview.rows[0]) == {"first_name", "last_name", "email"}
    assert preview.rows[0]["email"] == "student001@example.com"


# Parsing must not write anything. Only save() writes.
def test_parse_does_not_save(roster, db):
    roster.parse_upload((SAMPLES / "roster.csv").read_bytes())
    assert entries(db) == {}


# TC-02: a missing required column is named, with the expected headers, and nothing is saved.
def test_missing_email_column_is_named(roster, db):
    preview = roster.parse_upload((SAMPLES / "roster_bad.csv").read_bytes())
    assert preview.rows == []
    assert len(preview.errors) == 1
    assert 'דוא"ל' in preview.errors[0]
    assert entries(db) == {}


# TC-03: duplicate emails are listed (any letter case) and nothing is saved.
def test_duplicate_emails_are_listed(roster, db):
    preview = roster.parse_upload((SAMPLES / "roster_duplicates.csv").read_bytes())
    assert preview.rows == []
    assert "student001@example.com" in preview.errors[0]
    assert entries(db) == {}


def test_duplicates_ignore_letter_case(roster):
    data = csv_bytes("א,ב,A@example.com,1", "ג,ד,a@example.com,1")
    assert "a@example.com" in roster.parse_upload(data).errors[0]


# Emails are stored in lower case and trimmed, so matching on re-upload works.
def test_email_is_trimmed_and_lower_case(roster):
    preview = roster.parse_upload(csv_bytes("א,ב, Mixed@Example.COM ,1"))
    assert preview.rows[0]["email"] == "mixed@example.com"


# Excel and Moodle may add a BOM at the start. The first header must still be found.
def test_file_with_and_without_bom_is_read(roster):
    plain = csv_bytes("א,ב,a@example.com,1")
    with_bom = b"\xef\xbb\xbf" + plain
    assert roster.parse_upload(plain).errors == []
    assert roster.parse_upload(with_bom).errors == []


# A file that is not UTF-8 (for example an old Windows-1255 export) gets a clear error.
def test_file_that_is_not_utf8_is_rejected(roster):
    data = HEADER.encode("utf-8") + "א,ב,a@example.com,1\n".encode("windows-1255")
    preview = roster.parse_upload(data)
    assert preview.rows == []
    assert "UTF-8" in preview.errors[0]


# An empty file or a file with only the header has no students, so it is an error.
def test_empty_file_and_header_only_are_rejected(roster):
    assert roster.parse_upload(b"").errors
    assert roster.parse_upload(HEADER.encode("utf-8")).errors


# A row with an empty email cannot be matched later, so the file is rejected.
def test_row_with_empty_email_is_rejected(roster):
    preview = roster.parse_upload(csv_bytes("א,ב,,1"))
    assert preview.rows == [] and preview.errors


# The first save puts every row in the table as active, source "upload".
def test_save_stores_active_upload_entries(roster, db):
    preview = roster.parse_upload(csv_bytes("א,ב,a@example.com,1", "ג,ד,b@example.com,1"))
    roster.save(preview.rows)
    assert entries(db) == {"a@example.com": ("א", "ב", 1), "b@example.com": ("ג", "ד", 1)}
    assert [e["email"] for e in roster.list_active()] == ["a@example.com", "b@example.com"]


# TC-04 (D32): a new file replaces the roster, matched by lower-case email.
# Missing entries become inactive but are kept, so an old mark still points to its name.
def test_replace_matches_by_email_and_keeps_old_marks(roster, db):
    roster.save(roster.parse_upload(csv_bytes(
        "א,ב,a@example.com,1", "ג,ד,b@example.com,1", "ה,ו,c@example.com,1")).rows)
    a = roster.find_by_email("a@example.com")
    c = roster.find_by_email("c@example.com")
    # An old mark for entry c (a class session row is needed first).
    with closing(db.connect()) as conn, conn:
        conn.execute("INSERT INTO class_sessions (date) VALUES ('2026-11-17')")
        conn.execute(
            "INSERT INTO marks (session_id, roster_id, marked_at, source) VALUES (1, ?, 't', 'self')",
            (c["id"],))
    # New file: a has a new name, c is missing, d is new.
    roster.save(roster.parse_upload(csv_bytes(
        "אא,בב,A@example.com,1", "ג,ד,b@example.com,1", "ז,ח,d@example.com,1")).rows)
    state = entries(db)
    assert state["a@example.com"] == ("אא", "בב", 1)
    assert state["c@example.com"] == ("ה", "ו", 0)
    assert state["d@example.com"] == ("ז", "ח", 1)
    assert roster.find_by_email("a@example.com")["id"] == a["id"]  # same row, not a new one
    with closing(db.connect()) as conn:
        mark = conn.execute("SELECT roster_id FROM marks").fetchone()
    assert mark["roster_id"] == c["id"]
    assert sorted(e["email"] for e in roster.list_active()) == [
        "a@example.com", "b@example.com", "d@example.com"]


# An inactive student who appears in a later file becomes active again.
def test_entry_missing_then_back_becomes_active(roster, db):
    roster.save(roster.parse_upload(csv_bytes("א,ב,a@example.com,1", "ג,ד,b@example.com,1")).rows)
    roster.save(roster.parse_upload(csv_bytes("ג,ד,b@example.com,1")).rows)
    assert entries(db)["a@example.com"][2] == 0
    roster.save(roster.parse_upload(csv_bytes("א,ב,a@example.com,1", "ג,ד,b@example.com,1")).rows)
    assert entries(db)["a@example.com"][2] == 1


# save() checks duplicates again, because the rows come back from a browser form.
def test_save_refuses_duplicate_rows_and_writes_nothing(roster, db):
    rows = [
        {"first_name": "א", "last_name": "ב", "email": "a@example.com"},
        {"first_name": "ג", "last_name": "ד", "email": "a@example.com"},
    ]
    with pytest.raises(ValueError):
        roster.save(rows)
    assert entries(db) == {}


# Saving no rows would make every student inactive, so it is refused and the old roster stays.
def test_save_refuses_an_empty_list(roster, db):
    roster.save(roster.parse_upload(csv_bytes("א,ב,a@example.com,1")).rows)
    with pytest.raises(ValueError):
        roster.save([])
    assert entries(db)["a@example.com"][2] == 1


# find_by_email is case-insensitive and gives None when nobody matches.
def test_find_by_email(roster):
    roster.save(roster.parse_upload(csv_bytes("א,ב,a@example.com,1")).rows)
    assert roster.find_by_email("A@Example.com")["first_name"] == "א"
    assert roster.find_by_email("nobody@example.com") is None
