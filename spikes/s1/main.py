from datetime import datetime, timezone
from fastapi import FastAPI
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
