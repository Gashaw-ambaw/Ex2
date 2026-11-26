"""Builds the web app: connects the services and defines all the page addresses (routes)."""
import logging
import secrets
from pathlib import Path

import segno

from fastapi import Depends, FastAPI, Form, Request, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.attendance import AttendanceService, ScanTicket, parse_location
from app.clock import Clock
from app.comments import CommentService
from app.db import Db
from app.google import make_oauth
from app.identity import StudentIdentity
from app.lecturer import LecturerAccess
from app.qr_tokens import QrTokens
from app.roster import RosterService
from app.settings import Settings

TEMPLATES = Path(__file__).parent / "templates"


def create_app(settings=None, google=None):
    """Build the app. Run it with: uvicorn app.main:create_app --factory
    Tests pass a fake google; the real run uses the Google client."""
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
    app.state.identity = StudentIdentity(db, clock, app.state.roster, google or app.state.oauth.google)
    app.state.attendance = AttendanceService(
        db, clock, settings, QrTokens(settings.secret_key, settings.qr_rotate_sec, clock)
    )
    app.state.comments = CommentService(db, clock, settings)
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

    def qr_svg(address):
        # omitsize gives a viewBox, so CSS can scale the QR to the screen.
        return segno.make(address, error="m").svg_inline(omitsize=True, border=2)

    # Fixed texts for the ?done= address, so the address cannot put text on the page.
    done_messages = {"added": "Student added.", "email": "Email changed."}

    def roster_page(request, status_code=200, errors=(), saved=None, done=None):
        return templates.TemplateResponse(
            request,
            "roster.html",
            {
                "lecturer": True,
                "errors": list(errors),
                "saved": saved,
                "done": done_messages.get(done),
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

    # ---- Student pages: scan, Google sign-in, registration (UC-02, UC-03 steps 1-3) ----

    def student_page(request, message, status_code=200, link=None, button=None):
        return templates.TemplateResponse(
            request,
            "student.html",
            {"message": message, "link": link, "button": button},
            status_code=status_code,
        )

    def hello_page(request, entry, registered=False):
        greeting = f"Hello {entry['first_name']}, you are registered." if registered else f"Hello {entry['first_name']}."
        return templates.TemplateResponse(request, "mark.html", {"greeting": greeting})

    def read_location(lat, lon):
        # Empty, not a number or out of range all mean "denied" (UC-03 5d).
        try:
            lat, lon = float(lat), float(lon)
        except ValueError:
            return None
        return (lat, lon) if -90 <= lat <= 90 and -180 <= lon <= 180 else None

    @app.post("/mark")
    def mark(request: Request, lat: str = Form(""), lon: str = Form("")):
        ticket = request.session.get("ticket")
        if not ticket:
            return student_page(request, "Scan the QR in class first.", 400)
        try:
            result = app.state.attendance.mark(
                request.cookies.get("device"),
                ScanTicket(ticket["session_id"], ticket["scanned_at"]),
                read_location(lat, lon),
            )
        except ValueError as error:
            return student_page(request, str(error), 400)
        if result.outcome == "blocked":
            return student_page(
                request, "This phone already marked another student in this class. Ask the lecturer.", 400
            )
        if result.outcome == "already":
            return student_page(request, f"Already marked at {result.time}.")
        return student_page(request, f"Marked at {result.time}.")

    @app.get("/scan")
    def scan(request: Request, s: str = "", w: str = "", t: str = ""):
        try:
            ticket = app.state.attendance.check_scan(s, w, t)
        except ValueError as error:
            return student_page(request, str(error), 400)
        # The ticket lives in the signed session cookie (EDD 5). No database write.
        request.session["ticket"] = {"session_id": ticket.session_id, "scanned_at": ticket.scanned_at}
        owner = app.state.identity.device_owner(request.cookies.get("device"))
        if owner is not None:
            return hello_page(request, owner)
        return student_page(
            request, "To mark attendance, sign in once with Google.", link=("Sign in with Google", "/auth/start")
        )

    @app.get("/auth/start")
    async def auth_start(request: Request):
        if not request.session.get("ticket"):
            return student_page(request, "Scan the QR in class first.", 400)
        return await app.state.identity.start_sign_in(request, settings.redirect_uri)

    @app.get("/auth/callback")
    async def auth_callback(request: Request):
        # Only checks the sign-in. The email is kept in the signed cookie; nothing is written (D24).
        try:
            email = await app.state.identity.verify_google(request)
        except ValueError as error:
            return student_page(request, str(error), 400)
        request.session["email"] = email
        return student_page(
            request, f"Signed in as {email}.", button=("Confirm registration", "/register")
        )

    @app.post("/register")
    def register(request: Request):
        email = request.session.get("email")
        ticket = request.session.get("ticket")
        if not email or not ticket:
            return student_page(request, "Scan the QR in class first.", 400)
        device_id = request.cookies.get("device") or secrets.token_urlsafe(32)
        result = app.state.identity.confirm_registration(device_id, email)
        request.session.pop("email", None)
        if result.entry is None:
            return student_page(request, "Your email is not on the roster. Contact the lecturer.", 400)
        app.state.attendance.add_flags(ticket["session_id"], result.entry["id"], device_id, result.events)
        if app.state.attendance.ticket_is_fresh(ticket["scanned_at"]):
            reply = hello_page(request, result.entry, registered=True)
        else:
            request.session.pop("ticket", None)
            reply = student_page(request, "You are registered. Scan the QR again.")
        reply.set_cookie(
            "device",
            device_id,
            max_age=settings.browser_cookie_days * 86400,
            httponly=True,
            secure=settings.https_only,
            samesite="lax",
        )
        return reply

    # ---- The class page: comments (UC-06). No sign-in (D7, D10). ----

    def anon_id(request):
        """The random browser id for comments and polls (D27). Never linked to the device cookie or a student."""
        return request.cookies.get("anon") or secrets.token_urlsafe(32)

    def keep_anon(request, reply, anon):
        # The cookie is set once, when the browser has none.
        if request.cookies.get("anon") != anon:
            reply.set_cookie(
                "anon",
                anon,
                max_age=settings.browser_cookie_days * 86400,
                httponly=True,
                secure=settings.https_only,
                samesite="lax",
            )
        return reply

    def public_class_page(request, anon, status_code=200, error=None, text="", sent=False):
        session = app.state.attendance.session_for_today()
        own = app.state.comments.own(anon, session["id"]) if session else []
        reply = templates.TemplateResponse(
            request,
            "class_page.html",
            {"session": session, "own": own, "error": error, "text": text, "sent": sent},
            status_code=status_code,
        )
        return keep_anon(request, reply, anon)

    @app.get("/c")
    def student_class_page(request: Request, sent: str = ""):
        return public_class_page(request, anon_id(request), sent=sent == "1")

    @app.post("/c/comment")
    def send_comment(request: Request, text: str = Form("")):
        anon = anon_id(request)
        session = app.state.attendance.session_for_today()
        if session is None:
            # The page itself says "Class has not started". Nothing is stored.
            return public_class_page(request, anon, 400)
        try:
            app.state.comments.send(session["id"], anon, text)
        except ValueError as error:
            return public_class_page(request, anon, 400, error=str(error), text=text)
        return keep_anon(request, RedirectResponse("/c?sent=1", status_code=303), anon)

    # ---- Lecturer: the fixed QR and the comments (UC-07). The latest session, also from an earlier day. ----

    @app.get("/class/link", dependencies=guard)
    def class_link(request: Request):
        link = f"{settings.base_url}/c"
        return templates.TemplateResponse(
            request, "class_link.html", {"lecturer": True, "link": link, "qr_svg": qr_svg(link)}
        )

    @app.get("/comments", dependencies=guard)
    def comments_page(request: Request):
        return templates.TemplateResponse(
            request, "comments.html", {"lecturer": True, "refresh_ms": settings.refresh_sec * 1000}
        )

    @app.get("/comments/state", dependencies=guard)
    def comments_state():
        # Read only. The Comments page asks this every REFRESH_SEC seconds.
        session = app.state.attendance.latest_session()
        if session is None:
            return JSONResponse({"session": None, "comments": []})
        label = f"{session['date']}, {session['name']}" if session["name"] else session["date"]
        return JSONResponse({"session": label, "comments": app.state.comments.list_for_lecturer(session["id"])})

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
        svg = qr_svg(address) if address else None
        return JSONResponse(
            {"open": state.open, "seconds_left": state.seconds_left, "marks": state.marks,
             "flags": state.flags, "qr_svg": svg}
        )

    # ---- Review and export (UC-05). The latest session, also from an earlier day. ----

    def review_page(request, status_code=200, errors=()):
        attendance = app.state.attendance
        session = attendance.latest_session()
        context = {"lecturer": True, "errors": list(errors), "session": session}
        if session is not None:
            context["table"] = attendance.review_table(session["id"])
            context["without_mark"] = attendance.flags_without_mark(session["id"])
            context["unmarked"] = attendance.unmarked_entries(session["id"])
        return templates.TemplateResponse(request, "review.html", context, status_code=status_code)

    @app.get("/class/review", dependencies=guard)
    def review(request: Request):
        return review_page(request)

    @app.post("/class/review/status", dependencies=guard)
    def review_status(request: Request, mark_id: int = Form(0), status: str = Form("")):
        try:
            app.state.attendance.set_status(mark_id, status)
        except ValueError as error:
            return review_page(request, 400, errors=[str(error)])
        return RedirectResponse("/class/review", status_code=303)

    @app.post("/class/review/reset", dependencies=guard)
    def review_reset(mark_id: int = Form(0)):
        app.state.attendance.reset_mark(mark_id)
        return RedirectResponse("/class/review", status_code=303)

    @app.post("/class/review/add", dependencies=guard)
    def review_add(request: Request, roster_id: int = Form(0)):
        session = app.state.attendance.latest_session()
        if session is not None:
            try:
                app.state.attendance.add_manual(session["id"], roster_id)
            except ValueError as error:
                return review_page(request, 400, errors=[str(error)])
        return RedirectResponse("/class/review", status_code=303)

    @app.post("/class/review/export", dependencies=guard)
    def review_export(request: Request):
        session = app.state.attendance.latest_session()
        if session is None:
            return RedirectResponse("/class/review", status_code=303)
        try:
            data = app.state.attendance.export_csv(session["id"])
        except Exception:
            # UC-05 6a: say so; the table stays as it was.
            logging.exception("Export failed")
            return review_page(request, 500, errors=["Export failed. Try again."])
        name = f"attendance_{session['date']}.csv"
        return Response(
            data,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{name}"'},
        )

    @app.get("/roster", dependencies=guard)
    def roster(request: Request, saved: int | None = None, done: str | None = None):
        return roster_page(request, saved=saved, done=done)

    @app.post("/roster/add", dependencies=guard)
    def roster_add(request: Request, first_name: str = Form(""), last_name: str = Form(""), email: str = Form("")):
        try:
            app.state.roster.add_entry(first_name, last_name, email)
        except ValueError as error:
            return roster_page(request, 400, errors=[str(error)])
        return RedirectResponse("/roster?done=added", status_code=303)

    @app.post("/roster/email", dependencies=guard)
    def roster_email(request: Request, current_email: str = Form(""), new_email: str = Form("")):
        entry = app.state.roster.find_by_email(current_email)
        if entry is None:
            return roster_page(request, 400, errors=["No roster entry has that email."])
        try:
            app.state.roster.edit_email(entry["id"], new_email)
        except ValueError as error:
            return roster_page(request, 400, errors=[str(error)])
        return RedirectResponse("/roster?done=email", status_code=303)

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
