# Tools Report

Status: skeleton (25/11/2026). A tool is a row only after a real test; tools only considered go in "Alternative". Details are in `test_log.md`.

| Tool | Used for | Alternative | Real test | Result / limit |
|---|---|---|---|---|
| Python 3.13, FastAPI, uvicorn, Jinja2 | Web app and pages (D23) | [fill: ...] | test_log.md "S1 results"; "F1 live checks" | Worked on [fill: phone model, browser version]; load (S2) not verified |
| SQLite on a Railway Volume | Data store (D23) | [fill: ...] | test_log.md "S1 results" | Data kept after Redeploy; concurrent writes (S2) not verified |
| Railway | Hosting, HTTPS URL | [fill: ...] | test_log.md "S1 results" | Trial: up to 30 days, one-time $5 credit (Railway docs, 25/11, not tested) |
| Google sign-in (Authlib) | Student identity (D8) | [fill: ...] | test_log.md "S1 results"; "F1 live checks" | WhatsApp browser and 100-user cap not verified |
| Signed Starlette cookies | Lecturer session, scan ticket, device (D26, D27) | [fill: ...] | test_log.md "S1 results"; "F1 live checks" | 120-day lifetime not verified |
| segno 1.6.6 | QR on the projector page | [fill: ...] | test_log.md "F1 live checks" | Scan from about 3 m not verified |
| Browser Geolocation API | Class location button (D28) | [fill: ...] | test_log.md "F1 live checks" (laptop only) | Accuracy in the hall (S3) not verified |
| Mermaid | Diagrams in SDD, EDD, use cases | [fill: ...] | [fill: where, date] | Rendered correctly |
| pytest, FastAPI TestClient | Automated tests (stp.md) | [fill: ...] | Local run [fill: date] | 229 tests pass; phone flows are manual |

## Existing QR attendance systems (background, not tested)

[fill: up to 3 lines: which tools were looked at and why they were not used.]

## AI tools

Claude and Claude Code: see `AI_USAGE.md`.
