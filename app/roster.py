import csv
import io
import sqlite3
from collections import Counter
from contextlib import closing
from dataclasses import dataclass, field

# The three header names of the Moodle export (D30). Other columns are ignored.
HEADERS = {"first_name": "שם פרטי", "last_name": "שם משפחה", "email": 'דוא"ל'}


@dataclass
class RosterPreview:
    """What the lecturer sees before confirming. If errors is not empty, rows is empty."""

    rows: list = field(default_factory=list)
    errors: list = field(default_factory=list)


def _fail(message):
    return RosterPreview(errors=[message])


def _clean(rows):
    # Same cleaning for the upload and for the rows that come back from the form.
    return [
        {
            "first_name": r["first_name"].strip(),
            "last_name": r["last_name"].strip(),
            "email": r["email"].strip().lower(),
        }
        for r in rows
    ]


def _duplicates(rows):
    counts = Counter(r["email"] for r in rows)
    return sorted(email for email, n in counts.items() if n > 1)


def _valid_email(email):
    # Simple check only: one "@" with text on both sides. Google does the real check.
    name, at, domain = email.partition("@")
    return bool(name) and bool(at) and bool(domain) and "@" not in domain


class RosterService:
    """The course roster: read a CSV, check it, and save it (UC-00, FR-01)."""

    def __init__(self, db, clock):
        self._db = db
        self._clock = clock

    def parse_upload(self, data):
        # Reads the file in memory. Nothing is saved here.
        try:
            # utf-8-sig drops the BOM if the file has one.
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            return _fail("The file is not UTF-8. Save the Moodle export as CSV (UTF-8).")
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            return _fail("The file is empty.")
        missing = [name for name in HEADERS.values() if name not in reader.fieldnames]
        if missing:
            return _fail(
                "Missing column: " + ", ".join(missing)
                + ". Expected headers: " + ", ".join(HEADERS.values()) + "."
            )
        rows = []
        for number, line in enumerate(reader, start=2):  # line 1 is the header
            row = {key: (line.get(name) or "") for key, name in HEADERS.items()}
            if not row["email"].strip():
                return _fail(f"Line {number} has no email.")
            rows.append(row)
        if not rows:
            return _fail("The file has no students.")
        rows = _clean(rows)
        duplicates = _duplicates(rows)
        if duplicates:
            return _fail("Duplicate emails: " + ", ".join(duplicates))
        return RosterPreview(rows=rows)

    def save(self, rows):
        # The rows come back from a browser form, so they are cleaned and checked again.
        rows = _clean(rows)
        if not rows:
            raise ValueError("No students to save.")
        if _duplicates(rows):
            raise ValueError("Duplicate emails: " + ", ".join(_duplicates(rows)))
        now = self._clock.now_iso()
        # One transaction: either the whole roster is replaced or nothing changes.
        with closing(self._db.connect()) as conn, conn:
            for r in rows:
                conn.execute(
                    """INSERT INTO roster_entries (first_name, last_name, email, active, source, created_at)
                       VALUES (?, ?, ?, 1, 'upload', ?)
                       ON CONFLICT(email) DO UPDATE SET
                           first_name = excluded.first_name,
                           last_name = excluded.last_name,
                           active = 1""",
                    (r["first_name"], r["last_name"], r["email"], now),
                )
            # Not in the new file: inactive but kept, so old marks keep their name (D32).
            marks = ",".join("?" * len(rows))
            conn.execute(
                f"UPDATE roster_entries SET active = 0 WHERE email NOT IN ({marks})",
                [r["email"] for r in rows],
            )

    def list_active(self):
        with closing(self._db.connect()) as conn:
            return conn.execute("SELECT * FROM roster_entries WHERE active = 1 ORDER BY id").fetchall()

    def find_by_email(self, email):
        with closing(self._db.connect()) as conn:
            return conn.execute(
                "SELECT * FROM roster_entries WHERE email = ?", (email.strip().lower(),)
            ).fetchone()

    def add_entry(self, first_name, last_name, email):
        """Add one student by hand (UC-05 5a). An inactive entry with the same email comes back (D32)."""
        first, last, email = first_name.strip(), last_name.strip(), email.strip().lower()
        if not first or not last or not email:
            raise ValueError("First name, last name and email are required.")
        if not _valid_email(email):
            raise ValueError("The email is not valid.")
        with closing(self._db.connect()) as conn, conn:
            row = conn.execute("SELECT * FROM roster_entries WHERE email = ?", (email,)).fetchone()
            if row is not None and row["active"]:
                raise ValueError("This email is already on the roster.")
            if row is not None:
                conn.execute(
                    "UPDATE roster_entries SET first_name = ?, last_name = ?, active = 1 WHERE id = ?",
                    (first, last, row["id"]),
                )
            else:
                conn.execute(
                    "INSERT INTO roster_entries (first_name, last_name, email, active, source, created_at) "
                    "VALUES (?, ?, ?, 1, 'manual', ?)",
                    (first, last, email, self._clock.now_iso()),
                )
            return conn.execute("SELECT * FROM roster_entries WHERE email = ?", (email,)).fetchone()

    def edit_email(self, entry_id, email):
        """Change the email of one entry (UC-05 5c), for example when the roster email is not a Google account."""
        email = email.strip().lower()
        if not _valid_email(email):
            raise ValueError("The email is not valid.")
        with closing(self._db.connect()) as conn, conn:
            if conn.execute("SELECT 1 FROM roster_entries WHERE id = ?", (entry_id,)).fetchone() is None:
                raise ValueError("No such roster entry.")
            try:
                conn.execute("UPDATE roster_entries SET email = ? WHERE id = ?", (email, entry_id))
            except sqlite3.IntegrityError:
                raise ValueError("This email belongs to another roster entry.") from None
