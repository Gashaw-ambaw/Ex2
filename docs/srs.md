# Software Requirements Specification – Ex2 Web-based Teaching Tool

Status: draft. Date: 21/11/2026. Read with `decisions.md` (D1-D28).
This SRS says WHAT the system does. `decisions.md` says why, and the SDD says how. Use cases are in `use_cases.md`.

## 1. Introduction

### 1.1 Purpose
This document lists the requirements of the teaching tool, so the lecturer can check them and the tests can be derived from them.

### 1.2 Scope
Problem, scope and the five features (F1 to F5): `README.md`. F1, in-class attendance, is the main feature.

### 1.3 Definitions
- **Roster:** the list of students of the course (name and email), loaded from a Moodle export.
- **Class session:** one class on one date, created when the lecturer taps Start class (D19).
- **Attendance window:** the short period in which students can mark attendance.
- **Mark:** one attendance row for one roster entry in one class session.
- **Flag:** a warning shown to the lecturer only, for example "one device, two identities". It never blocks the student on its own, unless a requirement says so.
- **Status:** `normal` or `unverified`. **Source:** `self` (the student marked) or `manual` (the lecturer added the mark).
- **Device:** a browser identified by a cookie.

### 1.4 References
`README.md`, `decisions.md` (D1-D28), `use_cases.md` (UC-00 to UC-13), `sow.md`, `project_plan.md`, and the assignment text.

### 1.5 How requirements are written
- IDs follow D20: `FR-nn` (functional), `NFR-nn` (non-functional). Spikes are `S1-S6`, decisions `Dn`. An ID is never reused; a removed item is marked "retired".
- One functional requirement (FR) covers one use case: its goal, key rules and parameters, **including its alternative flows**. The alternative flows are verified by test cases in the STP, not by separate rows here. A few rows cover what cuts across use cases or is a safeguard (FR-16 to FR-20).
- **Priority:** Must is the core of a feature and its safeguards. Should is a target that is not guaranteed. Optional flows (Could) are not requirements; they are listed in Appendix C.
- **Marks on numbers:** MEASURED, ESTIMATE, "initial value: proposal" or OPEN. A proposal is not a decision.
- **Spike column:** a requirement names a spike if its value or its existence depends on it, even weakly. Section 2f is built from that column.
- Exact message and button texts are in `use_cases.md`, not here.

## 2. Overall description

### 2a Product perspective
A web application for in-class teaching. Students use an Android phone browser with no installation. The lecturer uses a page in any browser; the main assumption is a laptop, often projected. The external interfaces are in section 3.1.

### 2b User classes

| User class | Access | Source |
|---|---|---|
| Lecturer | one password | D14 |
| Registered student (F1) | Google sign-in, browser linked to a roster entry | D8; UC-02, UC-03 |
| Student (F2, F3) | none, anonymous | D10, D11; UC-06, UC-09 |
| Student (F5) | none | D13; UC-11 |

### 2c Operating environment
Android phone browsers for students (iPhone is not tested and not guaranteed); any browser for the lecturer, mainly a laptop. The system runs on Railway, an always-on host, Hobby plan with a usage limit (S1 done, D23).

### 2d Constraints (not requirements)

| Constraint | Source |
|---|---|
| Only students physically in class are counted | D1 |
| The photo only counts people; no face is identified | D2 |
| No integration with Moodle, Zoom or university systems; files are uploaded manually | D3 |
| A mobile web app with no installation | D4 |
| Real personal data never enters the repo | D5 |
| No network (IP) check for presence | D9 |
| F5 gives no grade; no code-similarity check; others' code is not run | D13 |
| Prefer existing tools and libraries | D17 |
| Built for the live demo; runs on Railway Hobby (D23); no production hosting, uptime or load guarantee | sow.md:22, 33 |

### 2e Assumptions
The assumptions are in `sow.md` section 6 (line 60) and are not copied here. One more: a class takes place on its date and is not postponed (D19).

### 2f Spike dependencies (derived from the Spike column)

| Spike | Requirements |
|---|---|
| S1 (hosting, HTTPS, cookies, Google sign-in) | FR-01, FR-03, FR-04, FR-09, FR-12, FR-14; NFR-01, NFR-02, NFR-06 |
| S2 (time-based QR, simultaneous marks) | FR-02, FR-04; NFR-03, NFR-05 |
| S3 (location in the hall) | FR-04; NFR-06 |
| S4 (head count) | FR-05 |
| S5 (F4 summary) | FR-12; NFR-10 |
| S6 (F5 report) | FR-13, FR-14, FR-19, FR-20; NFR-10 |

## 3. Specific requirements

### 3.1 External interfaces

| Interface | Used for | Source |
|---|---|---|
| Google sign-in | identify a student | D8; UC-02 |
| Android phone browser location | presence check | D9; UC-03 |
| Language-model API | F4 summary, F5 topic ratings | D12, D13, D17 |
| Audio extraction and transcription tool (for example ffmpeg) | F4 recording input (optional, Appendix C) | D12, D17; UC-10 |
| GitHub (public repos, read-only) | F5 repo check | D13; UC-11 |
| File upload and download | roster, photo, transcript, submissions list; attendance and review export | UC-00, UC-04, UC-10, UC-12, UC-05 |
| (none) Moodle, Zoom, university systems | no integration | D3 |

### 3.2 Functional requirements (all Must)

| ID | The system shall… | Feature | Source | Spike |
|---|---|---|---|---|
| FR-01 | let the lecturer load the course roster from a Moodle export saved as CSV (UTF-8, read by header name): read only first name, last name and email, review and remove non-student rows, save on the server only, keep earlier attendance rows when it is replaced; an invalid file is rejected without saving | F1 | UC-00 (including its alternative flows); D5, D30 | S1 |
| FR-02 | let the lecturer run an attendance window of `ATT_WINDOW_SEC` seconds with a full-screen QR that changes every `QR_ROTATE_SEC` seconds, a countdown and a live count of marks; close it on time or early; create today's class session when the lecturer taps Start class, if none exists, and open a window only in a started session; reject marks after closing | F1 | UC-01 (including its alternative flows, 1b deferred, D31); D7, D19 | S2 |
| FR-03 | let a student register a browser once with Google sign-in and a confirmation tap, matching the verified email to a roster entry (several devices allowed); refuse an email not on the roster; flag a browser re-linked to another student and a new device | F1 | UC-02 (including its alternative flows); D8, D16 | S1 |
| FR-04 | let a registered student mark with a scan and a confirmation within `SUBMIT_SEC` seconds, accepting only the current or previous QR rotation; one mark per roster entry per class; block and flag a device that marked another student; check the location within `LOC_RADIUS_M` metres of the class location set by the lecturer and store only yes/no (**OPEN / S3:** block or flag when out of range); if no class location is set, skip the check and warn on the lecturer page (proposal, S3; D28); record the roster entry, never a typed name or ID | F1 | UC-03 (including its alternative flows); D8, D9, D16; sow.md:16 | S1, S2, S3 |
| FR-05 | let the lecturer upload a class photo (at most `PHOTO_MAX_MB`) after the window closes, count the people in it (no faces identified), store the count, delete the photo, and alert when marks exceed the count by more than `GAP_TOLERANCE_PCT` percent; the alert never blocks or penalises anyone; if counting fails the lecturer can type a count | F1 | UC-04 (including its alternative flows); D2, D18 | S4 |
| FR-06 | let the lecturer review the session's attendance table (flagged marks first when the alert fired), set a mark to unverified or back to normal, add a late student (from the roster, or a student not on it), edit a roster email, and remove ("reset") a mark. A reset only removes the mark; a mark is added by hand (B5). Nothing is penalised automatically | F1 | UC-05 (s1-5, 3a, 4a, 5a, 5b, 5c, 5d); D16, D18 | |
| FR-07 | export the attendance table as a file (CSV or XLSX) with name, email, time, source, status and flags, keeping the table if the export fails | F1 | UC-05 (s6, 6a); assignment (the spreadsheet is the main feature) | |
| FR-08 | let a student send an anonymous comment of up to `COMMENT_MAX_CHARS` characters, at most once per `COMMENT_MIN_INTERVAL_SEC` seconds per browser, stored with time and session and no identity (in today's latest session when the class ended), and see their own comments | F2 | UC-06 (including its alternative flows); D10 | |
| FR-09 | let the lecturer read the comments of the current or latest session, newest first, refreshed every `REFRESH_SEC` seconds with a manual refresh control and an offline state | F2 | UC-07 (including its alternative flows); D10 | S1 |
| FR-10 | let the lecturer create a poll (a question, `POLL_OPTIONS_MIN` to `POLL_OPTIONS_MAX` options, an optional correct option), publish it, see the live count per option, close it and see the number of votes per option and right/wrong; starting a new poll closes an open one and keeps its results | F3 | UC-08 (including its alternative flows); D11 | |
| FR-11 | let a student see the active poll and give one anonymous answer per browser (random browser id, not changeable), and see the result after the poll closes | F3 | UC-09 (including its alternative flows); D11 | |
| FR-12 | let the lecturer upload a transcript (VTT or txt, at most `F4_UPLOAD_MAX_MB`), process it in the background with a status refreshed every `REFRESH_SEC` seconds, produce a short summary of at most `SUMMARY_MAX_WORDS` words (**OPEN**) with a language model, in the language of the transcript, which may be Hebrew (NFR-11), store the summary and delete the uploaded file; a failure shows a failed status | F4 | UC-10 (including its alternative flows); D12; sow.md:18 | S1, S5 |
| FR-13 | let a student paste a public repo link and get a report: layer 1 (code, no AI) checks file names against the checklist and the links in the README; layer 2 (a model) rates each checklist topic as absent, brief or detailed. The report marks what code checked and what a model rated, falls back to layer 1 when the model fails, and is not stored. It carries 3-5 remarks (**OPEN**, B2) and is written in the language of the README (NFR-11). When the lecturer has run the class review (FR-14), it also shows the class comparison, computed from the stored per-repo ratings; otherwise it shows none | F5 | UC-11 (including its alternative flows); UC-12 (s5, stored results); D13; sow.md:19, 31; README.md:42 | S6 |
| FR-14 | let the lecturer upload the submissions list (form responses export), read only the repo link column, clean and de-duplicate the links, and confirm. The system then reviews all repos in the background with a status refreshed every `REFRESH_SEC` seconds, applying layers 1 and 2. It stores the per-repo results and class counts (no emails), flags a private or missing repo and continues, shows a table with one row per repo, and deletes the uploaded file | F5 | UC-12 (including its alternative flows); D13 | S1, S6 |
| FR-15 | let the lecturer edit the review checklist in a text box (one item per line with the word to look for), validate and save it, pre-filled from the Ex1 To Do list and kept until changed | F5 | UC-13 (including its alternative flows); sow.md:19 | |
| FR-16 | provide a fixed class QR and a link to the class page, the entry point for comments, polls and the repo check | F2, F3, F5 | UC-06, UC-09, UC-11 (preconditions); D7 | |
| FR-17 | require the lecturer password for lecturer pages and limit repeated wrong attempts (after `LOGIN_ATTEMPT_LIMIT` wrong attempts, lock login for `LOGIN_LOCKOUT_SEC` seconds; the counter is in memory, D26) | All | UC-07 (1a), UC-08, UC-10, UC-12, UC-13 (lecturer signed in); D14; use_cases.md:7 | |
| FR-18 | require no sign-in on student pages for comments, polls and the repo check | F2, F3, F5 | UC-06, UC-09, UC-11; use_cases.md:7; D10, D11, D13 | |
| FR-19 | limit F5 abuse: one report per `F5_REPORT_INTERVAL_SEC` seconds per browser and at most `F5_DAILY_CAP` reports per day for the whole system (**value OPEN**) | F5 | UC-11 (s2, 2a, 2b); D13 | S6 |
| FR-20 | defend against prompt injection: cut a README longer than `README_MAX_CHARS` (**OPEN**, a proposal) and treat README text as data, never as instructions to the model | F5 | UC-11 (5c), UC-12 (s4); project_plan.md:67 | S6 |

### 3.3 Non-functional requirements

| ID | The system shall… | Feature | Priority | Source | Spike |
|---|---|---|---|---|---|
| NFR-01 | run in an Android phone browser with no installation (iPhone not tested, not guaranteed); supported browsers list **OPEN** | All | Must | D4; assignment; lecturer (B17) | S1 |
| NFR-02 | let a registered student mark with a scan and one tap after the one-time registration | F1 | Must | D8; README | S1 |
| NFR-03 | **TARGET (ESTIMATE, not a guarantee):** at least 95% of present students are marked within the window | F1 | Should | project_plan.md:11; sow.md:33 | S2 |
| NFR-04 | **TARGET (ESTIMATE, not a guarantee):** the lecturer needs 3-4 actions per class (open, photo, close, export), done through FR-02, FR-05 and FR-07 | F1 | Should | project_plan.md:12; sow.md:33; FR-02, FR-05, FR-07 | |
| NFR-05 | **TARGET:** handle simultaneous marks (`LOAD_SIM_MARKS`, **OPEN**) | F1 | Should | project_plan.md §2; sow.md:33 | S2 |
| NFR-06 | be served over HTTPS (browsers allow location only in a secure context; **not verified, check in S1**) | All | Must | project_plan.md §5 (S1) | S1, S3 |
| NFR-07 | keep the lecturer password in an environment variable and real personal data out of the repo; tests use synthetic data | All | Must | D14, D5 | |
| NFR-08 | store no ID numbers, and no identity with comments and poll answers | F1, F2, F3 | Must | D8, D10, D11 | |
| NFR-09 | apply one retention rule: everything stored is kept until the end of the semester, then deleted; uploaded files are deleted after processing; the F5 student report is not stored; F5 limit counters reset daily; the checklist and the class location are kept until changed | All | Must | D21 | |
| NFR-10 | stay under a provider spending limit for model calls in F4 and F5 (`MODEL_SPEND_LIMIT`, **OPEN**) | F4, F5 | Must | D13; sow.md:47 | S5, S6 |
| NFR-11 | show the user interface in English, and write summaries (F4) and reports (F5) in the language of the input (the transcript or the README) | All | Must | D22; use_cases.md (UI texts are in English) | |
| NFR-12 | run from a clean checkout with the README steps, and the tests run | All | Must | sow.md:20 | |

### 3.4 Parameters

| Name | Initial value | Mark | Source | Spike |
|---|---|---|---|---|
| `ATT_WINDOW_SEC` | 300 | initial value: proposal (changed 21/11) | use_cases.md:57 | S2 |
| `QR_ROTATE_SEC` | 10 | initial value, decided 22/11 | D7; use_cases.md:57 | S2 |
| `SUBMIT_SEC` | 60 | initial value: proposal (changed 21/11) | use_cases.md:102 | S2 |
| `LOC_RADIUS_M` | 50 | initial value: proposal; measured from the class location set by the lecturer in the app (no env var; value OPEN until S3) | D9, D28 | S3 |
| `GAP_TOLERANCE_PCT` | 5 | initial value: proposal | D18 | S4 |
| `PHOTO_MAX_MB` | 10 | initial value, decided 22/11 | use_cases.md:159 | S4 |
| `COMMENT_MAX_CHARS` | 300 | initial value: proposal | use_cases.md:204 | |
| `COMMENT_MIN_INTERVAL_SEC` | 10 | initial value: proposal | use_cases.md:205 | |
| `REFRESH_SEC` (lecturer pages, F4 and F5 status) | 20 | initial value: proposal | use_cases.md:218, 281, 332 | |
| `POLL_OPTIONS_MIN`, `POLL_OPTIONS_MAX` | 2 and 4 | decided (D11) | D11 | |
| `F4_UPLOAD_MAX_MB` | none | **OPEN** | use_cases.md:288 | S5 |
| `SUMMARY_MAX_WORDS` | none | **OPEN** | sow.md:18 | S5 |
| `F5_REPORT_INTERVAL_SEC` | 60 | initial value: proposal | use_cases.md:313; D13 | S6 |
| `F5_DAILY_CAP` | none | **OPEN** | D13; use_cases.md:314 | S6 |
| `README_MAX_CHARS` | none | **OPEN** | use_cases.md:320 | S6 |
| `MODEL_SPEND_LIMIT` | none | **OPEN** | D13; sow.md:47 | S5, S6 |
| `LOGIN_ATTEMPT_LIMIT` | 5 | decided 21/11 | D26; use_cases.md:224 | |
| `LOAD_SIM_MARKS` | 100 | initial value, decided 22/11 | NFR-05 | S2 |
| `LOGIN_LOCKOUT_SEC` | 300 | decided 21/11 (name: proposal) | D26 | |
| `LECTURER_SESSION_HOURS` | 8 | decided 21/11 (name: proposal) | D26 | |
| `BROWSER_COOKIE_DAYS` | 120 | decided 21/11 (name: proposal); device and anonymous cookies | D27 | |

`JOB_TIMEOUT_SEC` (OPEN, S5) is in Appendix C, because it applies only to the optional recording input.

### 3.5 Data (retention rule: D21)

| Item | Feature | Stored | Retention | Source |
|---|---|---|---|---|
| Roster (name, email) | F1 | yes, server only | end of semester; replaced on new upload | UC-00; D5, D21 |
| ID numbers | F1 | never | n/a | D8 |
| Device link, class session | F1 | yes | end of semester | UC-02, D19; D21 |
| Attendance row (roster entry, class, time, source, flags, status) | F1 | yes | end of semester | UC-03; D21 |
| Flag (kind, session, roster entry, device), also without a mark (blocked attempt, registration) | F1 | yes | end of semester | UC-02, UC-03; D16, D21 |
| Location | F1 | yes/no only | with the mark | D9 |
| Class location (a place set by the lecturer, not personal data) | F1 | yes | until the lecturer changes it | D21, D28 |
| Class photo | F1 | temporary | until counted | UC-04; D21 |
| Count and gap | F1 | yes | end of semester | UC-04; D21 |
| Comment | F2 | yes, with a random browser id (anonymous cookie), no identity | end of semester | D10; D21; D27 |
| Poll and answers (random browser id) | F3 | yes | end of semester | D11; D21 |
| Uploaded transcript or recording | F4 | temporary | until processed | UC-10; D21 |
| Summary | F4 | yes | end of semester | UC-10; D21 |
| F5 student report | F5 | no | n/a | UC-11; D21 |
| F5 limit counters | F5 | yes | reset daily | UC-11; D21 |
| Submissions list file | F5 | temporary | until processed | UC-12; D21 |
| F5 overview (no emails) | F5 | yes | end of semester | UC-12; D21 |
| Checklist | F5 | yes | until the lecturer changes it | UC-13; D21 |
| Job row (F4 summary, F5 class review) | F4, F5 | yes | end of semester | D21, D25 |

### 3.6 Threat model

| Threat | Control | Residual |
|---|---|---|
| Friend marked with a shared Google login | FR-03 (new-device flag), FR-05 (count alert) | `use_cases.md` Known limits 1 |
| One device marks several students | FR-04 (device block and flag) | Cookie bypass: Known limits 2 |
| Outside the room, or location spoofed | FR-04 (location), FR-05 | Deterrent, not proof (D9) |
| Forwarded photo of the QR | FR-02, FR-04 (rotating QR, short window) | D7 |
| Outsider comments or answers; a second browser answers again | FR-08 (rate limit), FR-11 (one answer per browser) | Known limits 3-4. The cause is open access by design (FR-18) |
| Wrong model output | FR-13 (marks what a model rated) | Known limits 5 |
| F5 daily cap used up by one person | FR-19 | Known limits 6 |
| Prompt injection in a README | FR-20 | Limit OPEN |
| Password guessing | FR-17 | Lockout after 5 wrong attempts for 300 s, counter in memory (D26); a lockout also blocks the real lecturer until it ends |
| Roster or real data leak | FR-01, NFR-07 | D5 |

## 4. Appendices

### Appendix A: traceability, use case to requirement

| UC | FR | Test |
|---|---|---|
| UC-00 | FR-01, FR-17 | |
| UC-01 | FR-02, FR-17 | |
| UC-02 | FR-03 | |
| UC-03 | FR-04 | |
| UC-04 | FR-05, FR-17 | |
| UC-05 | FR-06, FR-07, FR-17 | |
| UC-06 | FR-08, FR-16, FR-18 | |
| UC-07 | FR-09, FR-17 | |
| UC-08 | FR-10, FR-17 | |
| UC-09 | FR-11, FR-16, FR-18 | |
| UC-10 | FR-12, FR-17 | |
| UC-11 | FR-13, FR-16, FR-18, FR-19, FR-20 | |
| UC-12 | FR-13, FR-14, FR-17, FR-20 | |
| UC-13 | FR-15, FR-17 | |

The Test column is filled in the STP. Several test cases verify each FR. NFR-01 to NFR-12 are not traced to a use case; their source is a decision, the SoW or the plan.

### Appendix B: open items and notes

| # | Item |
|---|---|
| B1 | `sow.md:15` says each SRS requirement traces to a use case. The NFRs cite a decision, the SoW or the plan instead. |
| B2 | OPEN: `project_plan.md:67` ("show aggregates only") against `use_cases.md:307` ("3-5 remarks"). |
| B3 | OPEN / S3: block or flag for location (FR-04). |
| B4 | Decided (no decision ID; statuses follow D16 and D18): attendance statuses (normal and unverified only; source is a separate field) and the poll refresh (`REFRESH_SEC` with a manual refresh control). `use_cases.md` UC-08 step 3 now says 20 s. |
| B5 | Decided: a reset only removes the mark. The lecturer can add one by hand. Fixed in `use_cases.md` UC-05 5d. |
| B6 | OPEN numbers: supported browsers, `F4_UPLOAD_MAX_MB`, `SUMMARY_MAX_WORDS`, `F5_DAILY_CAP`, `README_MAX_CHARS`, `MODEL_SPEND_LIMIT`, `JOB_TIMEOUT_SEC`. |
| B7 | HTTPS (NFR-06): basis not verified, check in S1. The 95% and the 3-4 actions are ESTIMATE targets. |
| B8 | `sow.md:18` accepts a transcript or a short recording. The transcript is in FR-12; the recording is Appendix C. Hebrew is in scope. |
| B9 | D10 and D11 describe hide, delete and retry as part of the feature. They are optional (Appendix C), as decided. |
| B10 | The SoW cut order (F5 first, then F4; F1-F3 protected, `sow.md:53`) is a SoW fact; the Priority column does not encode it. |
| B11 | The STP must cover all 73 alternative flows counted in `use_cases.md` (3, 4, 6, 8, 4, 7, 5, 5, 4, 4, 6, 9, 6, 2 for UC-00 to UC-13). |
| B12 | "Device" means a browser (cookie); D16 and UC-09 use both words. |
| B13 | The F5 comparison with class counts is Must (FR-13), consistent with the assignment text (feature 5: "including comparisons to other students' work"), D13, `sow.md:19`, `sow.md:31` and `README.md:42`. It is limited to counts: the lecturer rejected a rubric (D13), and a similarity check needs a sandbox. |
| B14 | Decided 18/11, now D22: the user interface is in English; summaries and reports are written in the language of the input (NFR-11). |
| B15 | Decided 21/11 (D23): the demo runs on Railway, an always-on host (S1 done); Hobby plan with a usage limit (decided 22/11). |
| B16 | Decided 20/11: the lecturer may use any device with a browser; a laptop is the main assumption (2a, 2c). |
| B17 | Decided 20/11 (said by the lecturer): students use Android phone browsers. iPhone is not tested and not guaranteed (2a, 2c, 3.1, NFR-01). |

### Appendix C: optional flows (Could)

These are not requirements. They are cut first, in the SoW order: F5 first, then F4; F1-F3 are protected (`sow.md:53`).

| UC | Optional flows (in `use_cases.md`) |
|---|---|
| UC-00 to UC-04 | none |
| UC-05 | export to Google Sheets (not in `use_cases.md`; `sow.md:16`, `project_plan.md` open decision 6) |
| UC-06 | 4b (retry of an unsent comment) |
| UC-07 | s4-5, 4a, 4b, 4c (hide, show, delete, delete all) |
| UC-08 | 6a (delete a poll) |
| UC-09 | 3c (retry of an unsent answer) |
| UC-10 | recording input (s4, 4d, `JOB_TIMEOUT_SEC` OPEN); 4a (retry control); 4b (txt without timestamps); s6 (chapters, keywords, "related to", date, length); s7 (copy or download); 6a (delete the summary) |
| UC-11 | s7 (report download) |
| UC-12 | s3 (progress); s6 (sort and filter); s7 (export); 4c (stop the run); 6a (delete the overview) |
| UC-13 | s2 (minimum length); 3a (invalid-line error); 3b (reset to the default list) |
