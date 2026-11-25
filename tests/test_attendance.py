from contextlib import closing
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest

from app.attendance import CLOSED_MESSAGE, AttendanceService, ScanTicket, distance_m, parse_location
from app.qr_tokens import QrTokens

NOON = datetime(2026, 11, 24, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def service(db, clock, settings):
    clock.set(NOON)
    return AttendanceService(db, clock, settings, QrTokens(settings.secret_key, settings.qr_rotate_sec, clock))


def rows(db, sql):
    with closing(db.connect()) as conn:
        return [tuple(r) for r in conn.execute(sql).fetchall()]


def session_row(db, session_id):
    return rows(db, f"SELECT window_opened_at, window_ends_at, window_closed_at FROM class_sessions WHERE id = {session_id}")[0]


# ---- Start class (D19) ----

def test_no_session_before_start(service):
    assert service.session_for_today() is None


def test_start_class_creates_today_session(service, clock):
    session = service.start_class()
    assert session["date"] == clock.today().isoformat()
    assert service.session_for_today()["id"] == session["id"]


def test_start_class_twice_gives_the_same_session(service, db):
    first = service.start_class()
    second = service.start_class()
    assert first["id"] == second["id"]
    assert rows(db, "SELECT COUNT(*) FROM class_sessions") == [(1,)]


def test_session_date_is_the_israel_date(service, clock):
    # 23:30 UTC on 24/11 is already 25/11 in Israel (UTC+2 in winter).
    clock.set(datetime(2026, 11, 24, 23, 30, tzinfo=timezone.utc))
    assert service.start_class()["date"] == "2026-11-25"


def test_a_new_day_needs_a_new_session(service, clock):
    first = service.start_class()
    clock.set(NOON + timedelta(days=1))
    assert service.session_for_today() is None
    assert service.start_class()["id"] != first["id"]


# ---- The window (TC-05, TC-08, TC-09, TC-45) ----

def test_open_window_tc05(service, settings):
    session = service.start_class()
    service.open_window(session["id"])
    state = service.window_state(session["id"])
    assert state.open is True
    assert state.seconds_left == settings.att_window_sec == 300
    assert state.marks == 0
    assert state.flags == 0


def test_window_state_before_opening_is_closed(service):
    session = service.start_class()
    state = service.window_state(session["id"])
    assert state.open is False
    assert state.seconds_left == 0


def test_open_unknown_session_fails(service):
    with pytest.raises(ValueError):
        service.open_window(999)


def test_window_closes_by_itself_tc09(service, clock):
    session = service.start_class()
    service.open_window(session["id"])
    clock.set(NOON + timedelta(seconds=299))
    assert service.window_state(session["id"]).open is True
    assert service.window_state(session["id"]).seconds_left == 1
    clock.set(NOON + timedelta(seconds=300))
    assert service.window_state(session["id"]).open is False
    # No QR is valid after the window ends.
    assert service.current_qr(session["id"]) is None


def test_expiry_writes_nothing(service, db, clock):
    # Expiry is computed from window_ends_at; a read never changes the database.
    session = service.start_class()
    service.open_window(session["id"])
    before = session_row(db, session["id"])
    clock.set(NOON + timedelta(seconds=400))
    service.window_state(session["id"])
    service.current_qr(session["id"])
    assert session_row(db, session["id"]) == before
    assert before[2] is None


def test_close_early_tc08(service, db, clock):
    session = service.start_class()
    service.open_window(session["id"])
    clock.set(NOON + timedelta(seconds=30))
    service.close_window(session["id"])
    assert service.window_state(session["id"]).open is False
    assert service.current_qr(session["id"]) is None
    assert session_row(db, session["id"])[2] is not None


def test_close_twice_keeps_the_first_time(service, db, clock):
    session = service.start_class()
    service.open_window(session["id"])
    service.close_window(session["id"])
    first = session_row(db, session["id"])
    clock.set(NOON + timedelta(seconds=30))
    service.close_window(session["id"])
    assert session_row(db, session["id"]) == first


def test_totals_count_marks_and_flags_tc08(service, db):
    session = service.start_class()
    sid = session["id"]
    with closing(db.connect()) as conn, conn:
        conn.execute("INSERT INTO roster_entries (first_name, last_name, email, created_at) VALUES ('A', 'B', 'a@example.com', 'x')")
        conn.execute("INSERT INTO marks (session_id, roster_id, marked_at, source) VALUES (?, 1, 'x', 'manual')", (sid,))
        conn.execute("INSERT INTO flags (session_id, kind, created_at) VALUES (?, 'new_device', 'x')", (sid,))
        conn.execute("INSERT INTO flags (session_id, kind, created_at) VALUES (?, 'location', 'x')", (sid,))
    state = service.window_state(sid)
    assert (state.marks, state.flags) == (1, 2)
    assert service.count_marks(sid) == 1


@pytest.mark.parametrize("how", ["closed early", "expired"])
def test_open_after_close_is_refused_tc45(service, db, clock, how):
    session = service.start_class()
    service.open_window(session["id"])
    if how == "closed early":
        service.close_window(session["id"])
    else:
        clock.set(NOON + timedelta(seconds=301))
    before = session_row(db, session["id"])
    with pytest.raises(ValueError, match=CLOSED_MESSAGE):
        service.open_window(session["id"])
    assert session_row(db, session["id"]) == before


def test_closed_message_text():
    assert CLOSED_MESSAGE == "Attendance already closed for this session"


def test_open_while_open_changes_nothing(service, db, clock):
    # A double tap must not restart the 300 seconds.
    session = service.start_class()
    service.open_window(session["id"])
    before = session_row(db, session["id"])
    clock.set(NOON + timedelta(seconds=20))
    service.open_window(session["id"])
    assert session_row(db, session["id"]) == before


# ---- The QR address ----

def test_current_qr_is_a_valid_scan_address(service, settings, clock):
    session = service.start_class()
    service.open_window(session["id"])
    url = urlparse(service.current_qr(session["id"]))
    assert f"{url.scheme}://{url.netloc}" == settings.base_url
    assert url.path == "/scan"
    query = parse_qs(url.query)
    tokens = QrTokens(settings.secret_key, settings.qr_rotate_sec, clock)
    assert int(query["s"][0]) == session["id"]
    assert tokens.verify(session["id"], int(query["w"][0]), query["t"][0])


def test_current_qr_changes_every_rotation(service, clock, settings):
    session = service.start_class()
    service.open_window(session["id"])
    first = service.current_qr(session["id"])
    clock.set(NOON + timedelta(seconds=settings.qr_rotate_sec))
    assert service.current_qr(session["id"]) != first


def test_no_qr_before_opening(service):
    session = service.start_class()
    assert service.current_qr(session["id"]) is None


# ---- The class location (D28) ----

def test_no_location_at_first(service):
    assert service.class_location() is None


def test_set_and_replace_location(service):
    service.set_class_location(32.08, 34.78)
    assert service.class_location() == (32.08, 34.78)
    service.set_class_location(31.77, 35.21)
    assert service.class_location() == (31.77, 35.21)


@pytest.mark.parametrize("lat,lon", [(91, 0), (-91, 0), (0, 181), (0, -181)])
def test_location_out_of_range_is_refused(service, lat, lon):
    with pytest.raises(ValueError):
        service.set_class_location(lat, lon)
    assert service.class_location() is None


def test_parse_location():
    assert parse_location("32.08, 34.78") == (32.08, 34.78)
    assert parse_location("  -31.5 ,35 ") == (-31.5, 35.0)


@pytest.mark.parametrize("text", ["abc", "", "1", "1, 2, 3", "32.08; 34.78", "nan, 1", "inf, 1"])
def test_parse_location_bad_text(text):
    with pytest.raises(ValueError):
        parse_location(text)


# ---- A new session on the same day (UC-01 1b, D31) ----

def test_new_session_adds_a_second_session_today(service, db):
    first = service.start_class()
    service.open_window(first["id"])
    service.close_window(first["id"])
    second = service.new_session("Tutorial")
    assert second["id"] != first["id"]
    assert second["date"] == first["date"]
    assert second["name"] == "Tutorial"
    # The page and Start class now use the latest session.
    assert service.session_for_today()["id"] == second["id"]
    assert service.start_class()["id"] == second["id"]
    assert rows(db, "SELECT COUNT(*) FROM class_sessions") == [(2,)]


@pytest.mark.parametrize("name", [None, "", "   "])
def test_new_session_without_a_name_stores_null(service, name):
    service.start_class()
    assert service.new_session(name)["name"] is None


def test_new_session_trims_the_name(service):
    assert service.new_session("  Lab 2  ")["name"] == "Lab 2"


def test_new_session_can_open_a_window_and_the_old_one_stays(service, db, clock):
    first = service.start_class()
    service.open_window(first["id"])
    clock.set(NOON + timedelta(seconds=301))  # the first window expired
    old = session_row(db, first["id"])
    second = service.new_session(None)
    service.open_window(second["id"])
    assert service.window_state(second["id"]).open is True
    assert service.window_state(first["id"]).open is False
    assert session_row(db, first["id"]) == old
    # The old session keeps its marks.
    with closing(db.connect()) as conn, conn:
        conn.execute("INSERT INTO roster_entries (first_name, last_name, email, created_at) VALUES ('A', 'B', 'a@example.com', 'x')")
        conn.execute("INSERT INTO marks (session_id, roster_id, marked_at, source) VALUES (?, 1, 'x', 'manual')", (first["id"],))
    assert service.count_marks(first["id"]) == 1
    assert service.count_marks(second["id"]) == 0


def test_new_session_is_refused_while_the_window_is_open(service, db):
    session = service.start_class()
    service.open_window(session["id"])
    with pytest.raises(ValueError, match="Close attendance first"):
        service.new_session("Oops")
    assert rows(db, "SELECT COUNT(*) FROM class_sessions") == [(1,)]


def test_new_session_before_any_session_is_allowed(service):
    assert service.session_for_today() is None
    assert service.new_session(None)["id"] == service.session_for_today()["id"]


# ---- check_scan (UC-03 steps 1-2, TC-08 and TC-09 scan side) ----

def scan_parts(service, session_id):
    query = parse_qs(urlparse(service.current_qr(session_id)).query)
    return query["s"][0], query["w"][0], query["t"][0]


def test_check_scan_accepts_the_current_qr(service, clock):
    session = service.start_class()
    service.open_window(session["id"])
    ticket = service.check_scan(*scan_parts(service, session["id"]))
    assert ticket.session_id == session["id"]
    assert ticket.scanned_at == int(clock.now().timestamp())


def test_check_scan_accepts_the_previous_window(service, clock, settings):
    session = service.start_class()
    service.open_window(session["id"])
    parts = scan_parts(service, session["id"])
    clock.set(NOON + timedelta(seconds=settings.qr_rotate_sec))
    assert service.check_scan(*parts).session_id == session["id"]


def test_check_scan_refuses_an_older_window_tc12(service, clock, settings):
    session = service.start_class()
    service.open_window(session["id"])
    parts = scan_parts(service, session["id"])
    clock.set(NOON + timedelta(seconds=2 * settings.qr_rotate_sec))
    with pytest.raises(ValueError, match="Scan again"):
        service.check_scan(*parts)


def test_check_scan_refuses_a_wrong_token(service):
    session = service.start_class()
    service.open_window(session["id"])
    s, w, _ = scan_parts(service, session["id"])
    with pytest.raises(ValueError, match="Scan again"):
        service.check_scan(s, w, "0" * 16)


def test_check_scan_refuses_a_token_of_another_session_tc13(service, settings, clock):
    session = service.start_class()
    service.open_window(session["id"])
    _, w, _ = scan_parts(service, session["id"])
    other = QrTokens(settings.secret_key, settings.qr_rotate_sec, clock).make(session["id"] + 1, int(w))
    with pytest.raises(ValueError, match="Scan again"):
        service.check_scan(str(session["id"]), w, other)
    # A session number that does not exist is also "scan again".
    with pytest.raises(ValueError, match="Scan again"):
        service.check_scan(str(session["id"] + 1), w, other)


@pytest.mark.parametrize("s,w,t", [("", "", ""), ("x", "1", "abc"), ("1", "y", "abc"), ("1", "1", "")])
def test_check_scan_refuses_missing_or_bad_values(service, s, w, t):
    session = service.start_class()
    service.open_window(session["id"])
    with pytest.raises(ValueError, match="Scan again"):
        service.check_scan(s, w, t)


def test_check_scan_before_the_class_starts(service):
    with pytest.raises(ValueError, match="Class has not started"):
        service.check_scan("1", "1", "abc")


# TC-08 (scan side): after Close, the next scan gets "Attendance is closed".
def test_check_scan_after_close_tc08(service):
    session = service.start_class()
    service.open_window(session["id"])
    parts = scan_parts(service, session["id"])
    service.close_window(session["id"])
    with pytest.raises(ValueError, match="Attendance is closed"):
        service.check_scan(*parts)


# TC-09 (scan side): after ATT_WINDOW_SEC no QR is valid.
def test_check_scan_after_the_window_ends_tc09(service, clock):
    session = service.start_class()
    service.open_window(session["id"])
    parts = scan_parts(service, session["id"])
    clock.set(NOON + timedelta(seconds=300))
    with pytest.raises(ValueError, match="Attendance is closed"):
        service.check_scan(*parts)


def test_check_scan_when_the_window_was_never_opened(service):
    session = service.start_class()
    with pytest.raises(ValueError, match="Attendance is closed"):
        service.check_scan(str(session["id"]), "1", "abc")


# ---- The ticket (EDD 5: valid for SUBMIT_SEC) ----

def test_ticket_is_fresh_for_submit_sec(service, clock, settings):
    scanned = int(clock.now().timestamp())
    assert service.ticket_is_fresh(scanned) is True
    clock.set(NOON + timedelta(seconds=settings.submit_sec))
    assert service.ticket_is_fresh(scanned) is True
    clock.set(NOON + timedelta(seconds=settings.submit_sec + 1))
    assert service.ticket_is_fresh(scanned) is False


# ---- add_flags ----

def test_add_flags_writes_one_row_per_event(service, db):
    session = service.start_class()
    with closing(db.connect()) as conn, conn:
        conn.execute("INSERT INTO roster_entries (first_name, last_name, email, created_at) VALUES ('A', 'B', 'a@example.com', 'x')")
    service.add_flags(session["id"], 1, "dev-1", ["new_device", "relinked"])
    assert rows(db, "SELECT session_id, roster_id, device_id, kind FROM flags ORDER BY id") == [
        (session["id"], 1, "dev-1", "new_device"),
        (session["id"], 1, "dev-1", "relinked"),
    ]
    assert service.window_state(session["id"]).flags == 2


def test_add_flags_with_no_events_writes_nothing(service, db):
    session = service.start_class()
    service.add_flags(session["id"], 1, "dev-1", [])
    assert rows(db, "SELECT COUNT(*) FROM flags") == [(0,)]


def test_add_flags_refuses_an_unknown_kind(service, db):
    session = service.start_class()
    with pytest.raises(ValueError):
        service.add_flags(session["id"], 1, "dev-1", ["bogus"])
    assert rows(db, "SELECT COUNT(*) FROM flags") == [(0,)]


# ---- mark (UC-03 steps 5-6, TC-21 to TC-26) ----

HALL = (32.0853, 34.7818)
FAR = (32.1853, 34.7818)  # about 11 km north


@pytest.fixture
def marking(service, db, clock):
    """An open window, two roster entries (1 and 2) and two linked devices. Returns the ticket."""
    session = service.start_class()
    service.open_window(session["id"])
    with closing(db.connect()) as conn, conn:
        for first, email in (("A", "a@example.com"), ("B", "b@example.com")):
            conn.execute(
                "INSERT INTO roster_entries (first_name, last_name, email, created_at) VALUES (?, 'X', ?, 'x')",
                (first, email),
            )
        conn.execute("INSERT INTO devices (id, roster_id, created_at) VALUES ('dev-a', 1, 'x')")
        conn.execute("INSERT INTO devices (id, roster_id, created_at) VALUES ('dev-b', 2, 'x')")
    service.set_class_location(*HALL)
    return ScanTicket(session["id"], int(clock.now().timestamp()))


def marks(db):
    return rows(db, "SELECT session_id, roster_id, device_id, source, location_ok FROM marks ORDER BY id")


def flags(db):
    return rows(db, "SELECT roster_id, device_id, kind FROM flags ORDER BY id")


# TC-21: one mark, source self, only yes/no location. 12:00 UTC is 14:00 in Israel.
def test_mark_records_one_self_mark_tc21(service, db, marking):
    result = service.mark("dev-a", marking, HALL)
    assert (result.outcome, result.time) == ("marked", "14:00")
    assert marks(db) == [(marking.session_id, 1, "dev-a", "self", 1)]
    assert flags(db) == []


# TC-22: the tap comes within SUBMIT_SEC or not.
def test_mark_at_submit_sec_is_accepted_tc22(service, db, marking, clock, settings):
    clock.set(NOON + timedelta(seconds=settings.submit_sec))
    assert service.mark("dev-a", marking, HALL).outcome == "marked"


def test_mark_after_submit_sec_is_rejected_tc22(service, db, marking, clock, settings):
    clock.set(NOON + timedelta(seconds=settings.submit_sec + 1))
    with pytest.raises(ValueError, match="Scan the QR again"):
        service.mark("dev-a", marking, HALL)
    assert marks(db) == []


# TC-23: a second mark for the same roster entry shows the earlier time. Still one row, no flag.
def test_second_mark_shows_earlier_time_tc23(service, db, marking, clock):
    service.mark("dev-a", marking, HALL)
    clock.set(NOON + timedelta(seconds=20))
    again = service.mark("dev-a", marking, HALL)
    assert (again.outcome, again.time) == ("already", "14:00")
    assert len(marks(db)) == 1 and flags(db) == []


def test_second_device_of_the_same_student_gets_the_earlier_time_tc23(service, db, marking):
    service.mark("dev-a", marking, HALL)
    with closing(db.connect()) as conn, conn:
        conn.execute("INSERT INTO devices (id, roster_id, created_at) VALUES ('dev-a2', 1, 'x')")
    again = service.mark("dev-a2", marking, HALL)
    assert (again.outcome, again.time) == ("already", "14:00")
    assert len(marks(db)) == 1 and flags(db) == []


# TC-24: the window is closed.
def test_mark_after_close_tc24(service, db, marking):
    service.close_window(marking.session_id)
    with pytest.raises(ValueError, match="Attendance is closed; ask the lecturer"):
        service.mark("dev-a", marking, HALL)
    assert marks(db) == []


def test_mark_after_the_window_ends_tc24(service, db, marking, clock, settings):
    # A ticket scanned late in the window: the tap comes after the window ended.
    late = ScanTicket(marking.session_id, int(NOON.timestamp()) + settings.att_window_sec - 5)
    clock.set(NOON + timedelta(seconds=settings.att_window_sec + 1))
    with pytest.raises(ValueError, match="Attendance is closed; ask the lecturer"):
        service.mark("dev-a", late, HALL)
    assert marks(db) == []


# TC-25: a device that marked A tries B: blocked, flag device_reuse on the student who tapped.
def test_device_that_marked_a_cannot_mark_b_tc25(service, db, marking):
    service.mark("dev-a", marking, HALL)
    with closing(db.connect()) as conn, conn:
        conn.execute("UPDATE devices SET roster_id = 2 WHERE id = 'dev-a'")
    result = service.mark("dev-a", marking, HALL)
    assert result.outcome == "blocked"
    assert marks(db) == [(marking.session_id, 1, "dev-a", "self", 1)]
    assert flags(db) == [(2, "dev-a", "device_reuse")]


# TC-26: location out of range or denied: the mark is recorded with a flag. No class location: no check.
def test_out_of_range_marks_with_a_flag_tc26(service, db, marking):
    assert service.mark("dev-a", marking, FAR).outcome == "marked"
    assert marks(db) == [(marking.session_id, 1, "dev-a", "self", 0)]
    assert flags(db) == [(1, "dev-a", "location")]


def test_denied_location_marks_with_a_flag_tc26(service, db, marking):
    assert service.mark("dev-a", marking, None).outcome == "marked"
    assert marks(db) == [(marking.session_id, 1, "dev-a", "self", 0)]
    assert flags(db) == [(1, "dev-a", "location")]


def test_no_class_location_skips_the_check_tc26(service, db, marking):
    with closing(db.connect()) as conn, conn:
        conn.execute("DELETE FROM class_location")
    assert service.mark("dev-a", marking, None).outcome == "marked"
    assert marks(db) == [(marking.session_id, 1, "dev-a", "self", None)]
    assert flags(db) == []


# ---- extra ----

def test_distance_m_known_value():
    assert distance_m(32.0, 34.0, 32.001, 34.0) == pytest.approx(111.2, abs=1)


def test_an_unlinked_device_cannot_mark(service, db, marking):
    with pytest.raises(ValueError, match="Scan the QR in class first"):
        service.mark("dev-unknown", marking, HALL)
    assert marks(db) == []
