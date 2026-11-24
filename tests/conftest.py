import pytest

from app.settings import Settings


# A fixture gives each test the same ready-made input.
# tmp_path is a new empty folder for each test, so tests never share a database.
@pytest.fixture
def env(tmp_path):
    # Dummy values only. No real secrets in tests.
    return {
        "LECTURER_PASSWORD": "test-password",
        "SECRET_KEY": "test-secret-key",
        "GOOGLE_CLIENT_ID": "test-client-id",
        "GOOGLE_CLIENT_SECRET": "test-client-secret",
        "BASE_URL": "https://example.test/",
        "DB_PATH": str(tmp_path / "test.db"),
    }


# Settings built from the dummy environment above.
@pytest.fixture
def settings(env):
    return Settings.from_env(env)
