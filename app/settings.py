"""All settings in one place: secrets from environment variables, and the fixed numbers (limits, times)."""
import os
from dataclasses import dataclass, field

# Secrets and per-host values come from environment variables only (NFR-07).
REQUIRED = (
    "LECTURER_PASSWORD",
    "SECRET_KEY",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "BASE_URL",
    "DB_PATH",
)
# Only F4 and F5 use these two.
OPTIONAL = ("LLM_API_KEY", "GITHUB_TOKEN")


# frozen=True: the values cannot be changed after the object is made.
@dataclass(frozen=True)
class Settings:
    """All settings in one place: environment variables first, then the parameters."""

    # Secrets are left out of repr, so a log line or a traceback never shows them.
    lecturer_password: str = field(repr=False)
    secret_key: str = field(repr=False)
    google_client_id: str
    google_client_secret: str = field(repr=False)
    base_url: str
    db_path: str
    llm_api_key: str | None = field(default=None, repr=False)
    github_token: str | None = field(default=None, repr=False)

    # Parameters with decided values: SRS 3.4.
    att_window_sec: int = 300
    qr_rotate_sec: int = 10
    submit_sec: int = 60
    loc_radius_m: int = 50  # initial value, OPEN until spike S3
    gap_tolerance_pct: int = 5
    photo_max_mb: int = 10
    f4_upload_max_mb: int = 2
    summary_max_words: int = 600
    comment_max_chars: int = 300
    comment_min_interval_sec: int = 10
    refresh_sec: int = 20
    poll_options_min: int = 2
    poll_options_max: int = 4
    f5_report_interval_sec: int = 60
    f5_daily_cap: int = 50
    readme_max_chars: int = 20000
    login_attempt_limit: int = 5
    login_lockout_sec: int = 300
    lecturer_session_hours: int = 8
    browser_cookie_days: int = 120

    @classmethod
    def from_env(cls, env=None):
        # env is a dict. The app uses the real environment; tests pass their own dict.
        env = os.environ if env is None else env
        # An empty value counts as missing.
        missing = [name for name in REQUIRED if not env.get(name)]
        if missing:
            # Names only, never values.
            raise ValueError("Missing environment variables: " + ", ".join(missing))
        return cls(
            lecturer_password=env["LECTURER_PASSWORD"],
            secret_key=env["SECRET_KEY"],
            google_client_id=env["GOOGLE_CLIENT_ID"],
            google_client_secret=env["GOOGLE_CLIENT_SECRET"],
            # Remove a trailing "/" so that base_url + "/path" is always correct.
            base_url=env["BASE_URL"].rstrip("/"),
            db_path=env["DB_PATH"],
            llm_api_key=env.get("LLM_API_KEY") or None,
            github_token=env.get("GITHUB_TOKEN") or None,
        )

    @property
    def redirect_uri(self):
        # Google sends the user back to this address after sign-in (as in S1).
        return f"{self.base_url}/auth/callback"

    @property
    def https_only(self):
        # Secure cookies are sent only over HTTPS. Local runs over http need them off.
        return self.base_url.startswith("https")
