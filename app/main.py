from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.clock import Clock
from app.db import Db
from app.google import make_oauth
from app.settings import Settings


def create_app(settings=None):
    """Build the app. Run it with: uvicorn app.main:create_app --factory"""
    # Tests pass their own settings; the real run reads the environment.
    settings = settings or Settings.from_env()
    # Create the tables at start (safe to repeat).
    db = Db(settings.db_path)
    db.create_tables()

    app = FastAPI()
    # app.state holds the shared objects, so every route can use them.
    app.state.settings = settings
    app.state.db = db
    app.state.clock = Clock()
    app.state.oauth = make_oauth(settings)

    # The lecturer session is a signed cookie. max_age is set explicitly (EDD 6).
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        https_only=settings.https_only,
        same_site="lax",
        max_age=settings.lecturer_session_hours * 3600,
    )

    # Simple check that the server is running. No database access.
    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app
