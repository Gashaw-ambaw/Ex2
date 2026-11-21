import secrets
from datetime import datetime, timezone
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
def hello():
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return f"""<!doctype html>
<html><head><meta name="viewport" content="width=device-width, initial-scale=1">
<title>S1 Hello</title></head>
<body><h1>Hello from S1</h1><p>Server time (UTC): {now}</p></body></html>"""

@app.get("/health")
def health():
    return {"status": "ok"}

def _cookie_page(body: str) -> str:
    return f"""<!doctype html>
<html><head><meta name="viewport" content="width=device-width, initial-scale=1">
<title>S1 Cookie</title></head>
<body><h1>S1 cookie test</h1><p>{body}</p>
<p><a href="/cookie">Reload this page</a></p></body></html>"""

@app.get("/cookie", response_class=HTMLResponse)
def cookie_test(request: Request):
    value = request.cookies.get("s1_cookie")
    if value:
        return HTMLResponse(_cookie_page(f"Cookie found: {value}. The browser sent it back."))
    value = secrets.token_hex(4)
    response = HTMLResponse(_cookie_page(f"No cookie yet. I set one now: {value}. Reload to check."))
    response.set_cookie("s1_cookie", value, max_age=86400, httponly=True, secure=True, samesite="lax")
    return response