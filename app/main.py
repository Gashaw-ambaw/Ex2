from pathlib import Path

import segno

from fastapi import Depends, FastAPI, Form, Request, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.attendance import AttendanceService, parse_location
from app.clock import Clock
from app.db import Db
from app.google import make_oauth
from app.lecturer import LecturerAccess
from app.qr_tokens import QrTokens
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
    app.state.attendance = AttendanceService(
        db, clock, settings, QrTokens(settings.secret_key, settings.qr_rotate_sec, clock)
    )
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

    def class_page(request, status_code=200, errors=()):
        attendance = app.state.attendance
        session = attendance.session_for_today()
        return templates.TemplateResponse(
            request,
            "class.html",
            {
                "lecturer": True,
                "errors": list(errors),
                "session": session,
                "state": attendance.window_state(session["id"]) if session else None,
                "location": attendance.class_location(),
            },
            status_code=status_code,
        )

    # Simple check that the server is running. No database access.
    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/")
    def home():
        return RedirectResponse("/class", status_code=303)

    @app.get("/login")
    def login_form(request: Request):
        return templates.TemplateResponse(request, "login.html", {"message": None})

    @app.post("/login")
    def login(request: Request, password: str = Form("")):
        result = app.state.access.login(password)
        if result == "ok":
            request.session["lecturer"] = True
            return RedirectResponse("/class", status_code=303)
        if result == "locked":
            message = "Login locked. Try again in a few minutes."
        else:
            message = "Wrong password."
        return templates.TemplateResponse(request, "login.html", {"message": message})

    @app.post("/logout")
    def logout(request: Request):
        app.state.access.logout(request)
        return RedirectResponse("/login", status_code=303)

    @app.get("/class", dependencies=guard)
    def class_home(request: Request):
        return class_page(request)

    @app.post("/class/start", dependencies=guard)
    def class_start():
        app.state.attendance.start_class()
        return RedirectResponse("/class", status_code=303)

    @app.post("/class/new", dependencies=guard)
    def class_new(request: Request, name: str = Form("")):
        try:
            app.state.attendance.new_session(name)
        except ValueError as error:
            return class_page(request, 400, errors=[str(error)])
        return RedirectResponse("/class", status_code=303)

    @app.post("/class/location", dependencies=guard)
    def class_location(request: Request, location: str = Form("")):
        try:
            lat, lon = parse_location(location)
            app.state.attendance.set_class_location(lat, lon)
        except ValueError as error:
            return class_page(request, 400, errors=[str(error)])
        return RedirectResponse("/class", status_code=303)

    @app.post("/class/open", dependencies=guard)
    def class_open(request: Request):
        session = app.state.attendance.session_for_today()
        if session is None:
            return class_page(request, 400, errors=["Start class first."])
        try:
            app.state.attendance.open_window(session["id"])
        except ValueError as error:
            return class_page(request, 400, errors=[str(error)])
        return RedirectResponse("/class/qr", status_code=303)

    @app.post("/class/close", dependencies=guard)
    def class_close():
        session = app.state.attendance.session_for_today()
        if session is not None:
            app.state.attendance.close_window(session["id"])
        return RedirectResponse("/class", status_code=303)

    @app.get("/class/qr", dependencies=guard)
    def class_qr(request: Request):
        attendance = app.state.attendance
        session = attendance.session_for_today()
        if session is None or not attendance.window_state(session["id"]).open:
            return RedirectResponse("/class", status_code=303)
        return templates.TemplateResponse(
            request, "class_qr.html", {"lecturer": True, "refresh_ms": settings.qr_rotate_sec * 1000}
        )

    @app.get("/class/state", dependencies=guard)
    def class_state():
        # Read only. The QR page asks this every QR_ROTATE_SEC seconds.
        attendance = app.state.attendance
        session = attendance.session_for_today()
        if session is None:
            return JSONResponse({"open": False, "seconds_left": 0, "marks": 0, "flags": 0, "qr_svg": None})
        state = attendance.window_state(session["id"])
        address = attendance.current_qr(session["id"])
        # omitsize gives a viewBox, so CSS can scale the QR to the screen.
        svg = segno.make(address, error="m").svg_inline(omitsize=True, border=2) if address else None
        return JSONResponse(
            {"open": state.open, "seconds_left": state.seconds_left, "marks": state.marks,
             "flags": state.flags, "qr_svg": svg}
        )

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
