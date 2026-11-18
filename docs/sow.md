# Statement of Work – Ex2 Web-based Teaching Tool

Status: draft. Date: 18/11/2026. Client: the lecturer. Supplier: the student (one person).
Problem, scope and features: `README.md`. Requirements: SRS and `use_cases.md`.

## 1. Objectives

- A mobile web app for in-class attendance (F1, the main feature) that students use from a phone with no installation, and that the lecturer can trust.
- Four supporting features (F2 to F5, levels as in the README), shown in a live 10-minute demo in class.

## 2. Deliverables and acceptance criteria

| Deliverable | Acceptance criterion (checked by the lecturer) |
|---|---|
| Documents: tools report, SRS, use cases, SDD, EDD, test plan, results, AI_USAGE | Each file is in the repo, in English Markdown, and listed in the README. Each SRS requirement traces to a use case. |
| F1 Attendance (in depth) | With a synthetic roster, UC-00 to UC-05 run end to end. A student on the roster marks from a phone; a student not on the roster cannot. Presence is checked in three layers: a rotating QR code; location (out of range or denied: block or flag, decided after S3); a photo count that raises an alert when marks exceed it. A second student on the same device is blocked and flagged. The export is a file that opens in a spreadsheet (Google Sheets optional). The roster stays on the server and is never committed (D5); the photo is deleted after counting (UC-04). |
| F2 Comments, F3 Polls | UC-06 to UC-09: a comment appears on the lecturer page with no identity stored; a poll is created, answered, closed, and shows results. |
| F4 Lecture summary (thin slice) | UC-10 on one sample lecture (a Zoom transcript or a short recording) produces a short summary. The other D12 outputs (chapters, keywords, "related to") are not required. Transcripts may be in Hebrew (tested in S5). |
| F5 Repo report (thin slice) | UC-11 to UC-13 on two to three sample repos (in English) produce a report that marks what code checked and what a model rated. The checklist is edited in a text box and has a pre-filled default list. |
| Code, tests, quick start | A clean checkout runs with the steps in the README. The tests run. |
| Results document | States what passed, what failed and what was not tested. |
| Live demo | A 10-minute demo in class, with F1 shown end to end, on a temporary instance hosted by the supplier (hosting decided after S1). |

## 3. In scope and out of scope

**In scope:** the five features at the levels above, and the documents listed.

**Out of scope:**
- Zoom or remote attendance (D1); face recognition (D2); integration with Moodle, Zoom or university systems (D3); a native app (D4).
- Real personal data in the repo (D5); lecturer accounts (one password, D14).
- A code-similarity check between repos, and running other people's code. The F5 class comparison is counts only (D13). Grading.
- Cheat protection beyond the three layers above, the alert and the flags (D16, D18).
- Production hosting, support after the demo, and performance or load guarantees (to be measured, not promised).

## 4. Milestones (plan, to confirm)

| Date | Milestone |
|---|---|
| 18-19/11 | SoW. Repo documents brought up to date. Tools report. |
| 19-20/11 | SRS draft, human review, SRS closed. SDD, EDD, test plan. |
| 21-22/11 | F1 end to end on real phones. |
| 23/11 | F2, F3. |
| 24/11 | F4 and F5 thin slices, README, results. |
| 25/11 | Final check and submission (hour to confirm). |

Spikes S1 to S6 are inputs, not deliverables. S3 (location) needs a real class day (date to confirm). The demo date is to confirm.
There are no payment points. The cost is the supplier's time and the LLM API usage, measured in spikes S5 and S6, under a spending limit (D13).

## 5. Acceptance process

- The lecturer reviews each deliverable against the table in section 2. The evidence is the test plan run, recorded in `results.md`.
- A deliverable is done when its criterion is met, or the gap is written in `results.md`.
- If time runs out, F5 is cut first, then F4. F1 to F3 are protected.
- A change to the scope is requested in writing by the lecturer and accepted by the supplier.
- A rehearsal with 5-10 volunteers is planned before submission, with synthetic or consented data only.

## 6. Roles, assumptions, dependencies

- **Roles:** the lecturer accepts the work and supplies the roster export. The student designs, builds and documents, with AI assistance recorded in `AI_USAGE.md`.
- **Assumptions:** a Moodle roster export with name and email; every student has a smartphone and a Google account; Google sign-in works on phones (S1); the location check works in the hall (S3); an LLM API is available for F4 and F5 (provider and price: tools report).
- **Dependencies on the lecturer:** the demo date, the submission hour, the audience of the F5 report, permission to use the Ex1 repos as samples.