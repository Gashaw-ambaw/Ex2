"""Tests that the app starts and answers /health without writing to the database."""
from fastapi.testclient import TestClient

from app.main import create_app


# TestClient calls the app in memory, with no real server. base_url is https so secure cookies work.
def test_health_returns_ok(settings):
    client = TestClient(create_app(settings), base_url="https://testserver")
    reply = client.get("/health")
    assert reply.status_code == 200
    assert reply.json() == {"status": "ok"}


def test_health_does_not_write_to_the_database(settings):
    client = TestClient(create_app(settings), base_url="https://testserver")
    # Compare the whole database file before and after the call. It must be identical.
    path = settings.db_path
    with open(path, "rb") as f:
        before = f.read()
    client.get("/health")
    with open(path, "rb") as f:
        assert f.read() == before


def test_app_has_the_google_client_registered(settings):
    app = create_app(settings)
    assert hasattr(app.state.oauth, "google")
