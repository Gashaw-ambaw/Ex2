import pytest

from app.settings import Settings


# The env fixture is a plain dict, so no real environment variable is touched.
def test_reads_required_and_optional_names(env):
    env = {**env, "LLM_API_KEY": "llm", "GITHUB_TOKEN": "gh"}
    s = Settings.from_env(env)
    assert s.lecturer_password == "test-password"
    assert s.secret_key == "test-secret-key"
    assert s.google_client_id == "test-client-id"
    assert s.google_client_secret == "test-client-secret"
    assert s.db_path == env["DB_PATH"]
    assert s.llm_api_key == "llm"
    assert s.github_token == "gh"


def test_optional_names_default_to_none(settings):
    assert settings.llm_api_key is None
    assert settings.github_token is None


def test_base_url_loses_trailing_slash_and_gives_redirect_uri(settings):
    assert settings.base_url == "https://example.test"
    assert settings.redirect_uri == "https://example.test/auth/callback"


def test_missing_names_are_listed_without_values(env):
    del env["SECRET_KEY"]
    del env["DB_PATH"]
    with pytest.raises(ValueError) as error:
        Settings.from_env(env)
    message = str(error.value)
    assert "SECRET_KEY" in message and "DB_PATH" in message
    assert "test-password" not in message


def test_empty_value_counts_as_missing(env):
    env["LECTURER_PASSWORD"] = ""
    with pytest.raises(ValueError, match="LECTURER_PASSWORD"):
        Settings.from_env(env)


def test_parameters_have_the_srs_3_4_values(settings):
    assert settings.att_window_sec == 300
    assert settings.qr_rotate_sec == 10
    assert settings.submit_sec == 60
    assert settings.loc_radius_m == 50
    assert settings.gap_tolerance_pct == 5
    assert settings.photo_max_mb == 10
    assert settings.comment_max_chars == 300
    assert settings.comment_min_interval_sec == 10
    assert settings.refresh_sec == 20
    assert (settings.poll_options_min, settings.poll_options_max) == (2, 4)
    assert settings.f5_report_interval_sec == 60
    assert settings.login_attempt_limit == 5
    assert settings.login_lockout_sec == 300
    assert settings.lecturer_session_hours == 8
    assert settings.browser_cookie_days == 120


def test_secrets_are_not_in_repr(settings):
    text = repr(settings)
    for secret in ("test-password", "test-secret-key", "test-client-secret"):
        assert secret not in text


def test_https_only_follows_base_url_scheme(env):
    assert Settings.from_env(env).https_only is True
    env["BASE_URL"] = "http://localhost:8000"
    assert Settings.from_env(env).https_only is False
