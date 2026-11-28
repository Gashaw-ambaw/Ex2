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
| OpenCV 4.14.0.94 (headless), YOLOX-s from OpenCV Zoo (Apache-2.0) | Head count on the class photo (D37) | supervision, sahi (more dependencies); YOLOX-m (101 MB, not tried) | test_log.md "S4 spike"; "S4 live check" | Laptop: 11 of 11 within 10%, mean error 3.5%; Railway about 430 MB (approximate, Trial limit 1 GB); other halls not verified |
| Anthropic API, `claude-sonnet-5-5` (SDK 2.8.0) | F4 summary (D39) | Google AI Studio; Zoom AI summary (the lecturer's example, read only, not run): about 700 words, inconsistent spelling of the lecturer's name, mixed task numbers, judged by me | test_log.md "F4 live check" | Real Hebrew lecture of 45 minutes, structured summary: 4527 input and 1495 output tokens, about $0.02; length judged good by me; longer lectures not checked |
| Google AI Studio | Tested for the F4 summary, not chosen | Anthropic API | Manual, one real Hebrew transcript, 28/11 | Close result, one sample, judged by me; fits a future audio input |
| Mermaid | Diagrams in SDD, EDD, use cases | [fill: ...] | [fill: where, date] | Rendered correctly |
| pytest, FastAPI TestClient | Automated tests (stp.md) | [fill: ...] | Local run [fill: date] | 229 tests pass; phone flows are manual |

## Existing QR attendance systems (background, not tested)

[fill: up to 3 lines: which tools were looked at and why they were not used.]

## AI tools

Claude and Claude Code: see `AI_USAGE.md`.
