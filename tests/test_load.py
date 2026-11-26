"""TC-44 (S2): many marks at once on the real mark endpoint, on a local server."""

import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path

import httpx
import uvicorn

from app.main import create_app
from app.settings import Settings

ROSTER = Path(__file__).resolve().parents[1] / "sample_data" / "roster.csv"
MARKS = 100  # LOAD_SIM_MARKS (SRS 3.4)
HALL = (32.0853, 34.7818)


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_100_marks_at_once_tc44(env):
    port = free_port()
    base_url = f"http://127.0.0.1:{port}"
    # http, so the cookies are sent without the Secure flag.
    settings = Settings.from_env({**env, "BASE_URL": base_url})
    app = create_app(settings)

    # Synthetic students, each with a linked phone (the same method /register uses, without Google).
    rows = app.state.roster.parse_upload(ROSTER.read_bytes()).rows[:MARKS]
    app.state.roster.save(rows)
    devices = [f"dev-{number:03}" for number in range(MARKS)]
    for device, row in zip(devices, rows):
        app.state.identity.confirm_registration(device, row["email"])

    attendance = app.state.attendance
    session_id = attendance.start_class()["id"]
    attendance.set_class_location(*HALL)
    attendance.open_window(session_id)

    # One uvicorn worker, as on Railway.
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()

    started_at = []
    # All students tap together: the barrier opens when the last one has scanned.
    barrier = threading.Barrier(MARKS, action=lambda: started_at.append(time.perf_counter()), timeout=60)

    def student(device):
        with httpx.Client(
            base_url=base_url, cookies={"device": device}, timeout=settings.submit_sec, trust_env=False
        ) as client:
            scan = client.get(attendance.current_qr(session_id).removeprefix(base_url))
            assert scan.status_code == 200
            barrier.wait()
            reply = client.post("/mark", data={"lat": str(HALL[0]), "lon": str(HALL[1])})
            return reply.status_code, reply.text, time.perf_counter()

    try:
        deadline = time.monotonic() + 10
        while not server.started:
            assert time.monotonic() < deadline, "the server did not start"
            time.sleep(0.05)
        with ThreadPoolExecutor(max_workers=MARKS) as pool:
            replies = list(pool.map(student, devices))
    finally:
        server.should_exit = True
        server_thread.join(timeout=10)

    seconds = max(done for _, _, done in replies) - started_at[0]
    print(f"\nTC-44: {len(replies)} marks in {seconds:.1f} s")

    failed = [(status, text) for status, text, _ in replies if status != 200 or "Marked at" not in text]
    assert len(replies) == MARKS and not failed, failed[:3]
    # Each student is recorded once.
    with closing(app.state.db.connect()) as conn:
        counts = tuple(
            conn.execute(
                "SELECT COUNT(*), COUNT(DISTINCT roster_id), COUNT(DISTINCT device_id) FROM marks WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        )
    assert counts == (MARKS, MARKS, MARKS)
    # A reply later than SUBMIT_SEC would be too late: the ticket is stale by then.
    assert seconds < settings.submit_sec
