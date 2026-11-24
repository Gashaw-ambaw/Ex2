from pathlib import Path

from fastapi import Depends, FastAPI, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.clock import Clock
from app.db import Db
from app.google import make_oauth
from app.lecturer import LecturerAccess
from app.roster import RosterService
from app.settings import Settings

TEMPLATES = Path(__file__).parent / "templates"


def create_app(settings=None):
    """Build the app. Run it with: uvicorn app.main:create_app --factory"""
    # Tests pass their own settings; the real run reads the environment.
    settings = settings or Settings.from_env()
    # Create the tables at start (safe to repeat).
    db = Db(settings.db_path)
    db.create_tables()

    app = FastAPI()
    # app.state holds the shared objects, so every route can use them.
    clock = Clock()
    app.state.settings = settings
    app.state.db = db
    app.state.clock = clock
    app.state.oauth = make_oauth(settings)
    app.state.access = LecturerAccess(settings, clock)
    app.state.roster = RosterService(db, clock)
    templates = Jinja2Templates(directory=str(TEMPLATES))

    # The lecturer session is a signed cookie. max_age is set explicitly (EDD 6).
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        https_only=settings.https_only,
        same_site="lax",
        max_age=settings.lecturer_session_hours * 3600,
    )

    # Every lecturer route lists this. Without a login it redirects to /login.
    def lecturer_only(request: Request):
        app.state.access.require_lecturer(request)

    guard = [Depends(lecturer_only)]

    def roster_page(request, status_code=200, errors=(), saved=None):
        return templates.TemplateResponse(
            request,
            "roster.html",
            {
                "lecturer": True,
                "errors": list(errors),
                "saved": saved,
                "active_count": len(app.state.roster.list_active()),
            },
            status_code=status_code,
        )

    # Simple check that the server is running. No database access.
    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/")
    def home():
        # Step 4 will put the class page here.
        return RedirectResponse("/roster", status_code=303)

    @app.get("/login")
    def login_form(request: Request):
        return templates.TemplateResponse(request, "login.html", {"message": None})

    @app.post("/login")
    def login(request: Request, password: str = Form("")):
        result = app.state.access.login(password)
        if result == "ok":
            request.session["lecturer"] = True
            return RedirectResponse("/roster", status_code=303)
        if result == "locked":
            message = "Login locked. Try again in a few minutes."
        else:
            message = "Wrong password."
        return templates.TemplateResponse(request, "login.html", {"message": message})

    @app.post("/logout")
    def logout(request: Request):
        app.state.access.logout(request)
        return RedirectResponse("/login", status_code=303)

    @app.get("/roster", dependencies=guard)
    def roster(request: Request, saved: int | None = None):
        return roster_page(request, saved=saved)

    @app.post("/roster/upload", dependencies=guard)
    async def roster_upload(request: Request, file: UploadFile):
        # The file is read in memory and never written to disk (D21).
        data = await file.read()
        preview = app.state.roster.parse_upload(data)
        if preview.errors:
            return roster_page(request, 400, errors=preview.errors)
        return templates.TemplateResponse(
            request, "roster_preview.html", {"lecturer": True, "rows": preview.rows}
        )

    @app.post("/roster/confirm", dependencies=guard)
    def roster_confirm(
        request: Request,
        first_name: list[str] = Form([]),
        last_name: list[str] = Form([]),
        email: list[str] = Form([]),
        keep: list[int] = Form([]),
    ):
        if not len(first_name) == len(last_name) == len(email):
            return roster_page(request, 400, errors=["The form is incomplete. Upload the file again."])
        # Only the ticked rows are saved. Numbers outside the list are ignored.
        chosen = set(keep)
        rows = [
            {"first_name": f, "last_name": l, "email": e}
            for i, (f, l, e) in enumerate(zip(first_name, last_name, email))
            if i in chosen
        ]
        try:
            app.state.roster.save(rows)
        except ValueError as error:
            return roster_page(request, 400, errors=[str(error)])
        return RedirectResponse(f"/roster?saved={len(rows)}", status_code=303)

    return app
