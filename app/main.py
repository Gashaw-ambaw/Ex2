"""Builds the web app: connects the services and defines all the page addresses (routes)."""
import logging
import secrets
from pathlib import Path

import segno

from fastapi import Depends, FastAPI, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.attendance import AttendanceService, ScanTicket, parse_location
from app.clock import Clock
from app.comments import CommentService
from app.db import Db
from app.google import make_oauth
from app.headcount import HeadCountService
from app.identity import StudentIdentity
from app.jobs import JobRunner
from app.lecturer import LecturerAccess
from app.llm import LlmGateway
from app.people_counter import PeopleCounter
from app.polls import PollService
from app.qr_tokens import QrTokens
from app.roster import RosterService
from app.settings import Settings
from app.summaries import HINT as TRANSCRIPT_HINT
from app.summaries import SummaryService

TEMPLATES = Path(__file__).parent / "templates"


def create_app(settings=None, google=None, counter=None, llm=None, spawn=None):
    """Build the app. Run it with: uvicorn app.main:create_app --factory
    Tests pass fakes (google, counter, llm) and their own spawn for jobs; the real run uses the real ones."""
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
    app.state.headcount = HeadCountService(db, clock, settings, app.state.attendance, counter or PeopleCounter())
    app.state.comments = CommentService(db, clock, settings)
    app.state.polls = PollService(db, clock, settings)
    # A new random id for each server run (D25).
    app.state.jobs = JobRunner(db, clock, secrets.token_hex(8), spawn)
    app.state.jobs.fail_dead_jobs()
    app.state.summaries = SummaryService(db, clock, settings, app.state.jobs, llm or LlmGateway(settings))
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

    # ---- The class page: comments and polls (UC-06, UC-09). No sign-in (D7, D10, D11). ----

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

    def public_class_page(request, anon, status_code=200, **notes):
        """notes: error, text and sent (comment form); answered and refused (poll)."""
        session = app.state.attendance.session_for_today()
        context = {"session": session, "own": [], "poll": None, **notes}
        if session is not None:
            context["own"] = app.state.comments.own(anon, session["id"])
            poll = app.state.polls.active(session["id"])
            if poll is not None:
                context["poll"] = poll
                context["choice"] = app.state.polls.answer_of(poll["id"], anon)
                # Votes go to the student's page only after the poll is closed.
                context["results"] = None if poll["open"] else app.state.polls.results(poll["id"])
        reply = templates.TemplateResponse(request, "class_page.html", context, status_code=status_code)
        return keep_anon(request, reply, anon)

    @app.get("/c")
    def student_class_page(request: Request, sent: str = "", answered: str = ""):
        return public_class_page(request, anon_id(request), sent=sent == "1", answered=answered == "1")

    @app.post("/c/answer")
    def send_answer(request: Request, poll_id: int = Form(0), option: int = Form(-1)):
        anon = anon_id(request)
        session = app.state.attendance.session_for_today()
        if session is None:
            return public_class_page(request, anon, 400)
        outcome = app.state.polls.answer(session["id"], poll_id, anon, option)
        if outcome == "not accepted":
            return public_class_page(request, anon, 400, refused=True)
        # "already": the plain page says "You answered".
        address = "/c?answered=1" if outcome == "ok" else "/c"
        return keep_anon(request, RedirectResponse(address, status_code=303), anon)

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

    # ---- Lecturer: polls (UC-08). The latest session, also from an earlier day. ----

    def polls_page(request, status_code=200, errors=()):
        session = app.state.attendance.latest_session()
        poll = app.state.polls.active(session["id"]) if session else None
        return templates.TemplateResponse(
            request,
            "polls.html",
            {
                "lecturer": True,
                "errors": list(errors),
                "session": session,
                "poll": poll,
                "results": app.state.polls.results(poll["id"]) if poll else None,
                "max_options": settings.poll_options_max,
                "refresh_ms": settings.refresh_sec * 1000,
            },
            status_code=status_code,
        )

    @app.get("/polls", dependencies=guard)
    def polls_home(request: Request):
        return polls_page(request)

    @app.get("/polls/state", dependencies=guard)
    def polls_state():
        # Read only. results() gives only the number of answers while the poll is open (D36).
        session = app.state.attendance.latest_session()
        poll = app.state.polls.active(session["id"]) if session else None
        if poll is None:
            return JSONResponse({"open": False, "answered": 0})
        return JSONResponse(app.state.polls.results(poll["id"]))

    @app.post("/polls/start", dependencies=guard)
    def polls_start(
        request: Request,
        question: str = Form(""),
        option1: str = Form(""),
        option2: str = Form(""),
        option3: str = Form(""),
        option4: str = Form(""),
        correct: str = Form(""),
    ):
        session = app.state.attendance.session_for_today()
        if session is None:
            return polls_page(request, 400, errors=["Start class first."])
        # The form counts the fields from 1, the service from 0. An unreadable value becomes a refused one.
        chosen = None
        if correct:
            chosen = int(correct) - 1 if correct in ("1", "2", "3", "4") else -1
        try:
            app.state.polls.start(session["id"], question, [option1, option2, option3, option4], chosen)
        except ValueError as error:
            return polls_page(request, 400, errors=[str(error)])
        return RedirectResponse("/polls", status_code=303)

    @app.post("/polls/close", dependencies=guard)
    def polls_close(poll_id: int = Form(0)):
        app.state.polls.close(poll_id)
        return RedirectResponse("/polls", status_code=303)

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

    # ---- Class photo count (UC-04). ----

    # A plain def: FastAPI runs it in a thread, so counting does not stop other requests.
    @app.post("/class/photo", dependencies=guard)
    def class_photo(request: Request, photo: UploadFile | None = File(None)):
        attendance = app.state.attendance
        session = attendance.session_for_today()
        if session is None:
            return class_page(request, 400, errors=["Start class first."])
        if not session["window_opened_at"] or attendance.window_state(session["id"]).open:
            return class_page(request, 400, errors=["Close attendance first."])
        # One byte more than the limit is enough to see that the file is too large.
        data = photo.file.read(settings.photo_max_mb * 1024 * 1024 + 1) if photo else b""
        try:
            app.state.headcount.count_photo(session["id"], data)
        except ValueError as error:
            return class_page(request, 400, errors=[str(error)])
        return RedirectResponse("/class/review", status_code=303)

    # ---- Lecture summary (UC-10). The latest session only (D40). ----

    def summary_page(request, status_code=200, errors=()):
        summaries = app.state.summaries
        session = app.state.attendance.latest_session()
        job = summaries.latest_job()
        context = {
            "lecturer": True,
            "errors": list(errors),
            "session": session,
            "configured": summaries.configured,
            "running": job is not None and job["status"] == "running",
            "failed": job is not None and job["status"] == "failed",
            "summary": summaries.summary(session["id"]) if session else None,
            "refresh_sec": settings.refresh_sec,
        }
        return templates.TemplateResponse(request, "summary.html", context, status_code=status_code)

    @app.get("/summary", dependencies=guard)
    def summary(request: Request):
        return summary_page(request)

    @app.post("/summary", dependencies=guard)
    def upload_transcript(request: Request, transcript: UploadFile | None = File(None)):
        session = app.state.attendance.latest_session()
        if session is None:
            return summary_page(request, 400)  # The page itself says "Start class first."
        if not app.state.summaries.configured:
            return summary_page(request, 400)  # The page itself says "Summary is not set up."
        if transcript is None or not transcript.filename:
            return summary_page(request, 400, errors=[TRANSCRIPT_HINT])
        # One byte more than the limit is enough to see that the file is too large.
        data = transcript.file.read(settings.f4_upload_max_mb * 1024 * 1024 + 1)
        try:
            app.state.summaries.start(session["id"], transcript.filename, data)
        except ValueError as error:
            return summary_page(request, 400, errors=[str(error)])
        return RedirectResponse("/summary", status_code=303)

    # ---- Review and export (UC-05). The latest session, also from an earlier day. ----

    def review_page(request, status_code=200, errors=()):
        attendance = app.state.attendance
        session = attendance.latest_session()
        context = {"lecturer": True, "errors": list(errors), "session": session}
        if session is not None:
            context["table"] = attendance.review_table(session["id"])
            context["head"] = app.state.headcount.result(session["id"])
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
