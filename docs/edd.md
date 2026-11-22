# Engineering Design Document

Status: draft. Date: 21/11/2026. Read with `sdd.md`, `srs.md` and `decisions.md` (D1-D28). IDs follow D20.
Tags: [A] assignment, [SRS], [SDD], [UC] `use_cases.md`, [Dn] decision, [U21] my answer 21/11/2026, [S1] spike S1 (`results.md`), [code] checked in the installed library, [P] proposal (not a decision), [U22] my answer 22/11/2026.

## 1. Scope and stack

- This EDD gives the low-level class and sequence diagrams [A], the schema and the session details that the SDD leaves to it (sdd.md:4). F1 (FR-01 to FR-07) is in depth; F2-F3 are short; F4-F5 are thin [D6].
- Stack: Python 3.13, FastAPI, uvicorn with one worker, SQLite through plain `sqlite3` (no ORM), Jinja2 pages with a little JS for polling, Authlib for Google sign-in, `segno` for the QR (not verified) [U21, S1]. Host: Railway Hobby with a usage limit [U21, U22].
- One worker is required, because the job boot-id rule and the in-memory login counter depend on it [U21, S1]. Every data-changing action is a POST, and no GET writes to the database [U21, S1].
- C-01 is five thin controllers with routes only and no logic [U21]. Each other component is one service class with its SQL in private methods [U21]. One `app/` package with one module per component (for example `roster.py`, `attendance.py`); tests in `tests/` [U22].
- Infrastructure classes (not components) [U21]: `Settings` (env vars and parameters), `Db` (one sqlite3 connection per call; creates the tables), `Clock` (UTC now, Israel time for display; set in tests), `JobRunner` (the S1 job design).
- Times are stored in UTC and shown in Israel time [U21]. A session date is the Israel date [P].

## 2. Class diagrams

### 2.1 F1 (C-01 to C-06)

All services also use `Db` and `Clock`; those arrows are left out.

```mermaid
classDiagram
  class AttendanceController {
    +login()
    +logout()
    +upload_roster()
    +start_class()
    +set_class_location()
    +open_attendance()
    +close_attendance()
    +window_state()
    +scan()
    +google_login()
    +google_callback()
    +confirm_registration()
    +confirm_mark()
    +upload_photo()
    +review()
    +export()
  }
  class LecturerAccess {
    +login(password) LoginResult
    +logout(session)
    +require_lecturer(request)
  }
  class RosterService {
    +parse_upload(file) RosterPreview
    +save(entries)
    +find_by_email(email) RosterEntry
    +add_entry(name, email)
    +edit_email(entry_id, email)
    +list_active() list
  }
  class StudentIdentity {
    +start_sign_in(request)
    +verify_google(request) str
    +confirm_registration(device_id, email) RegisterResult
    +device_owner(device_id) RosterEntry
  }
  class AttendanceService {
    +start_class() ClassSession
    +session_for_today() ClassSession
    +new_session(name) ClassSession
    +set_class_location(lat, lon)
    +open_window(session_id)
    +close_window(session_id)
    +window_state(session_id) WindowState
    +current_qr(session_id) str
    +check_scan(s, w, t) ScanTicket
    +mark(device_id, ticket, location) MarkResult
    +add_flags(session_id, events)
    +count_marks(session_id) int
    +review_table(session_id, flagged_first) list
    +set_status(mark_id, status)
    +add_manual(session_id, roster_id)
    +reset_mark(mark_id)
    +export_csv(session_id) bytes
  }
  class QrTokens {
    +make(session_id, window) str
    +verify(session_id, window, token) bool
  }
  class HeadCountService {
    +count_photo(session_id, image) CountResult
    +set_manual_count(session_id, count) CountResult
    +result(session_id) CountResult
  }
  class PeopleCounter {
    <<interface>>
    +count(image) int
  }
  class Google {
    <<external>>
  }
  class Db
  class Clock
  class RosterEntry {
    +id
    +first_name
    +last_name
    +email
    +active
  }
  class Device {
    +id
    +roster_id
  }
  class ClassSession {
    +id
    +date
    +name
    +window_ends_at
    +window_closed_at
  }
  class Mark {
    +session_id
    +roster_id
    +device_id
    +source
    +status
    +location_ok
  }
  class Flag {
    +session_id
    +roster_id
    +device_id
    +kind
  }
  class HeadCount {
    +session_id
    +count
    +gap
    +alert
  }
  class ClassLocation {
    +lat
    +lon
  }
  class ScanTicket {
    +session_id
    +scanned_at
  }
  AttendanceController ..> LecturerAccess
  AttendanceController ..> RosterService
  AttendanceController ..> StudentIdentity
  AttendanceController ..> AttendanceService
  AttendanceController ..> HeadCountService
  StudentIdentity ..> RosterService
  StudentIdentity ..> Google
  AttendanceService ..> StudentIdentity
  AttendanceService ..> RosterService
  AttendanceService ..> QrTokens
  HeadCountService ..> AttendanceService : count_marks
  HeadCountService ..> PeopleCounter
  AttendanceService ..> Db
  RosterService --> RosterEntry
  StudentIdentity --> Device
  AttendanceService --> ClassSession
  AttendanceService --> Mark
  AttendanceService --> Flag
  AttendanceService --> ClassLocation
  AttendanceService --> ScanTicket
  HeadCountService --> HeadCount
  RosterEntry "1" --> "*" Device
  ClassSession "1" --> "*" Mark
```

- C-06 calls C-05 `count_marks()`. C-05 never calls C-06 [SDD:48, U21]. For "flagged first", the controller asks `HeadCountService.result()` and passes the alert to `review_table()`.
- `PeopleCounter` hides the count method. Option A or B stays OPEN until S4 [SDD:134].
- `RegisterResult` carries the roster entry and the events (`new_device`, `relinked`). The controller passes them to `add_flags()`, so C-04 never calls C-05 [P].
- `new_session(name)` is deferred (1b, D31).

### 2.2 F2-F5 (C-07 to C-11, Must methods only)

```mermaid
classDiagram
  class CommentsController
  class PollsController
  class SummaryController
  class ReviewController
  class CommentService {
    +send(session_id, anon_id, text)
    +own(anon_id) list
    +list_for_lecturer(session_id) list
  }
  class PollService {
    +start(session_id, question, options, correct)
    +close(poll_id)
    +active(session_id) Poll
    +answer(poll_id, anon_id, option)
    +results(poll_id)
  }
  class SummaryService {
    +start(session_id, file) int
    +job_status(job_id)
    +summary(session_id) Summary
  }
  class RepoReviewService {
    +student_report(anon_id, url) Report
    +start_class_review(file) int
    +overview() list
    +checklist() str
    +save_checklist(text)
  }
  class LlmGateway {
    +complete(instructions, data_text) str
  }
  class GitHubClient {
    +file_list(url)
    +readme(url)
  }
  class JobRunner {
    +start(kind, work) int
    +status(job_id)
    +fail_dead_jobs()
  }
  class AttendanceService {
    +session_for_today() ClassSession
  }
  class Db
  CommentsController ..> CommentService
  PollsController ..> PollService
  SummaryController ..> SummaryService
  ReviewController ..> RepoReviewService
  CommentService ..> AttendanceService
  PollService ..> AttendanceService
  SummaryService ..> JobRunner
  SummaryService ..> LlmGateway
  RepoReviewService ..> JobRunner
  RepoReviewService ..> LlmGateway
  RepoReviewService ..> GitHubClient
  JobRunner ..> Db
```

Entities: `Comment`, `Poll`, `Answer`, `Summary`, `Job`, `RepoResult`, `Checklist`; their fields are in section 3. Login and logout routes are in `AttendanceController` [U21].

## 3. Schema

SQLite, times as UTC ISO text [U21]. Fields and keys are [P] unless tagged. "Delete" means the end-of-semester script deletes the rows [SDD, D21].

| Table | Fields and keys | Owner | Delete |
|---|---|---|---|
| `roster_entries` | id PK, first_name, last_name, email UNIQUE (lower case), active, source (upload / manual), created_at | C-03 | yes |
| `devices` | id PK (the random cookie value), roster_id FK, created_at | C-04 | yes |
| `class_sessions` | id PK, date, name (null; D19), window_opened_at, window_ends_at, window_closed_at. No unique date: D19 1b allows a second session | C-05 | yes |
| `marks` | id PK, session_id FK, roster_id FK, device_id (null if manual), marked_at, source (self / manual), status (normal / unverified), location_ok (1 / 0 / null). UNIQUE(session_id, roster_id); UNIQUE(session_id, device_id) where device_id is not null | C-05 | yes |
| `flags` | id PK, session_id FK, roster_id, device_id, kind (new_device / relinked / device_reuse / location), created_at | C-05 | yes |
| `class_location` | id = 1, lat, lon, updated_at [U21] | C-05 | **no** [U21] |
| `head_counts` | session_id PK FK, count, source (auto / manual), marks_at_count, gap, alert, created_at | C-06 | yes |
| `comments` | id PK, session_id FK, anon_id, text, hidden, created_at | C-07 | yes |
| `polls` | id PK, session_id FK, question, options_json, correct_index (null), status (open / closed), created_at, closed_at. UNIQUE(status) where status = 'open' | C-08 | yes |
| `poll_answers` | PK(poll_id, anon_id), option_index, created_at [FR-11] | C-08 | yes |
| `summaries` | id PK, session_id FK, text, created_at | C-10 | yes |
| `jobs` | id PK, kind (summary / class_review), status, progress, total, boot_id, created_at, finished_at, error. UNIQUE(kind) where status = 'running' [S1, U21] | JobRunner | yes [U21] |
| `repo_results` | id PK, job_id FK, repo_url, accessible, layer1_json, ratings_json, flags, created_at. No emails [FR-14] | C-11 | yes |
| `f5_reports` | id PK, anon_id, created_at. Gives the per-browser interval and the daily cap by date [SDD:90] | C-11 | yes |
| `checklist` | id = 1, text, updated_at | C-11 | **no** [D21] |

- The login attempt counter is not stored; it lives in memory in `LecturerAccess` [U21].
- Uploaded files (roster, photo, transcript, submissions list) are never stored in a table. They are deleted after processing, also on failure [D21, SDD:90]. The photo is read in memory only [P].
- Registration looks only at active roster entries. Marking checks only the device link [U21].

## 4. Sequences

The actors (Lecturer, Student) are people; every other participant is a class in section 2.

### 4.1 UC-01 Run an attendance window (with Start class)

```mermaid
sequenceDiagram
  actor L as Lecturer
  participant AC as AttendanceController
  participant LA as LecturerAccess
  participant RS as RosterService
  participant AS as AttendanceService
  participant QT as QrTokens
  participant DB as Db
  opt roster not loaded yet (UC-00, FR-01)
    L->>AC: POST roster file
    AC->>RS: parse_upload(file), then save(entries) after the lecturer confirms
  end
  L->>AC: POST Start class
  AC->>LA: require_lecturer(request)
  AC->>AS: start_class()
  AS->>DB: insert today's session if none exists
  opt class location not set, or the room changed
    L->>AC: POST location (Use my current location, or pasted lat, lon)
    AC->>AS: set_class_location(lat, lon)
  end
  L->>AC: POST Open attendance
  AC->>AS: open_window(session_id)
  Note over AS: No started session gives Start class first. A closed window shows "Attendance already closed for this session" (D19 1b, deferred, D31).
  AS->>DB: window_ends_at = now + ATT_WINDOW_SEC
  loop every QR_ROTATE_SEC until the window ends
    L->>AC: GET window state (JSON)
    AC->>AS: window_state(session_id), current_qr(session_id)
    AS->>QT: make(session_id, window)
    AC-->>L: QR SVG, count, seconds left
  end
  L->>AC: POST Close (or the time is up)
  AC->>AS: close_window(session_id)
  AC-->>L: totals, marks and flags
```

The location control sits on the Start class page: a "Use my current location" button (browser geolocation) and a text field for "lat, lon" copied from Google Maps [U21].

### 4.2 UC-02 Register device

```mermaid
sequenceDiagram
  actor S as Student
  participant AC as AttendanceController
  participant SI as StudentIdentity
  participant G as Google
  participant RS as RosterService
  participant AS as AttendanceService
  participant DB as Db
  Note over S,AC: Reached only from UC-03 step 3, when the mark page finds no device cookie
  S->>AC: GET Sign in with Google
  AC->>SI: start_sign_in(request)
  SI-->>S: redirect to Google
  S->>G: choose an account
  G-->>S: redirect to the callback with a code
  S->>AC: GET callback
  AC->>SI: verify_google(request)
  SI->>G: exchange the code, require email_verified
  SI-->>AC: verified email
  AC-->>S: email kept in the signed session cookie (no DB write), page with Confirm registration
  S->>AC: POST Confirm registration
  AC->>SI: confirm_registration(device_id, email)
  SI->>RS: find_by_email(email), active entries only
  alt email not on the roster
    AC-->>S: contact the lecturer, no registration
  else entry found
    SI->>DB: insert or re-link the device
    SI-->>AC: RegisterResult (entry, events new_device or relinked)
    AC->>AS: add_flags(session_id, events)
    alt scan ticket still valid (at most SUBMIT_SEC)
      AC-->>S: set the device cookie, continue at UC-03 step 3
    else ticket expired
      AC-->>S: set the device cookie, scan again (once per device)
    end
  end
```

### 4.3 UC-03 Mark attendance

```mermaid
sequenceDiagram
  actor S as Student
  participant AC as AttendanceController
  participant AS as AttendanceService
  participant QT as QrTokens
  participant SI as StudentIdentity
  participant DB as Db
  S->>AC: GET scan URL (s, w, t)
  AC->>AS: check_scan(s, w, t)
  AS->>QT: verify(s, w, t), w is the current or previous window
  AS-->>AC: ScanTicket, or expired so scan again
  AC->>SI: device_owner(device cookie)
  alt no device
    AC-->>S: ticket kept in the session cookie, Sign in with Google (UC-02)
  else registered
    AC-->>S: ticket kept in the session cookie, Hello name. Mark you present?
  end
  S->>AC: POST I'm here, with the browser location or denied
  AC->>AS: mark(device_id, ticket, location)
  AS->>AS: ticket age at most SUBMIT_SEC, window open
  AS->>AS: distance to the class location against LOC_RADIUS_M gives location_ok
  AS->>DB: insert the mark
  alt roster entry already marked
    AC-->>S: earlier time, no second mark
  else this device marked another student
    AS->>DB: flag device_reuse
    AC-->>S: blocked
  else inserted
    AS->>DB: flag location if out of range or denied
    AC-->>S: Marked at HH:MM (Israel time)
  end
```

### 4.4 UC-04 Class photo count (and UC-05 review)

```mermaid
sequenceDiagram
  actor L as Lecturer
  participant AC as AttendanceController
  participant LA as LecturerAccess
  participant HC as HeadCountService
  participant PC as PeopleCounter
  participant AS as AttendanceService
  participant DB as Db
  L->>AC: POST photo (window closed, at most PHOTO_MAX_MB)
  AC->>LA: require_lecturer(request)
  AC->>HC: count_photo(session_id, image)
  HC->>PC: count(image), in memory
  alt count fails
    HC-->>AC: failed
    AC-->>L: form to type a count, then set_manual_count
  else counted
    HC->>AS: count_marks(session_id)
    HC->>HC: gap and alert (section 5)
    HC->>DB: save the head_counts row
  end
  Note over HC: The photo is dropped in every case and never written to disk
  AC->>AS: review_table(session_id, flagged_first = alert)
  AC-->>L: alert with flagged marks first, or No gap
  L->>AC: POST unverified, manual add or reset (FR-06)
  AC->>AS: set_status, add_manual or reset_mark
  L->>AC: POST Export (FR-07)
  AC->>AS: export_csv(session_id)
  AC-->>L: CSV file
```

### 4.5 F4 background job (UC-10)

```mermaid
sequenceDiagram
  actor L as Lecturer
  participant SC as SummaryController
  participant SS as SummaryService
  participant JR as JobRunner
  participant LG as LlmGateway
  participant DB as Db
  L->>SC: POST transcript (VTT or txt, at most F4_UPLOAD_MAX_MB)
  SC->>SS: start(session_id, file)
  SS->>JR: start(summary, work)
  JR->>DB: insert a running job, a second start is refused by the unique key
  JR-->>SC: job id, returns at once
  par job thread
    JR->>SS: work, read the text and delete the file
    SS->>LG: complete(instructions, transcript as data)
    SS->>DB: save the summary
    JR->>DB: status done, or failed on an error
  and status page
    loop every REFRESH_SEC
      L->>SC: GET job status
      SC->>SS: job_status(job_id)
    end
  end
  Note over JR,DB: After a restart, a running row with another boot id is shown as failed (S1)
```

## 5. Algorithms

- **QR token** [U21; details P]: w = floor(now / `QR_ROTATE_SEC`); t = HMAC-SHA256(`SECRET_KEY`, "session_id:w"), first 16 hex characters. A scan is accepted when t matches (constant-time compare), w is the current or previous window, and the window is open.
- **Scan ticket** [U21]: {session_id, scanned_at} in the signed session cookie. A mark is accepted while now - scanned_at is at most `SUBMIT_SEC` (60, initial value, proposal). If the ticket expires during the first Google sign-in, the student scans again, once per device.
- **Distance** [U21; formula P]: haversine distance from the browser location to the class location; location_ok = distance at most `LOC_RADIUS_M`. Location denied gives 0 and a flag (UC-03 5d). No class location set: no check, location_ok null, and a warning on the lecturer page [P, approved 21/11, to confirm in S3].
- **Count gap** [P]: marks = all marks of the session when the count is made; gap = marks - count; alert when marks > count x (1 + `GAP_TOLERANCE_PCT` / 100). Example (UC-04): 104 marks, 97 counted, limit 101.85, so the alert fires.
- **Roster replace** [P]: entries are matched by lower-case email. Entries missing from the new file become inactive and are kept, so old marks keep their name (FR-01).
- **Export** [U21]: CSV, UTF-8 with BOM; columns name, email, time, source, status, flags (FR-07).

## 6. Cookies, login and jobs

| Cookie | Holds | Lifetime | Source |
|---|---|---|---|
| `session` (Starlette, signed with `SECRET_KEY`, https_only, SameSite Lax) | lecturer flag; Google sign-in state; verified email until Confirm registration; scan ticket | `LECTURER_SESSION_HOURS` = 8, `max_age` set explicitly (the default is 14 days) | U21; S1; code; name P |
| `device` | random id linked to a roster entry | `BROWSER_COOKIE_DAYS` = 120 | U21; name P |
| `anon` | random id for comments, polls and F5 limits; never stored with a device id or roster id | `BROWSER_COOKIE_DAYS` = 120 | U21 |

- `device` and `anon` are HttpOnly, Secure, SameSite Lax, like the S1 cookie test [P]. A cleared device cookie means signing in again and a `new_device` flag [D16]. The 120-day lifetime is not verified (S1 tested short gaps only).
- Starlette renews the signature timestamp only when the session changes [code].
- Login: after `LOGIN_ATTEMPT_LIMIT` = 5 wrong passwords, login is locked for everyone for `LOGIN_LOCKOUT_SEC` = 300 [U21; name P]. The counter is in memory and resets on restart [U21]. The password is compared in constant time [P]. Logout is a POST button on every lecturer page [U21].
- Jobs [S1, U21]: one `jobs` table for F4 and F5, one running job per kind, a thread in the same process, and a boot id per server run. A running row with another boot id is shown as failed. The page polls every `REFRESH_SEC`. The F5 student report is synchronous [SDD:86].

## 7. Errors

- A database error gives a short error page with status 500 [S1]. A wrong type or a file that is too large gives an error, and nothing is stored (UC-00 2a, UC-04 1a, UC-10 2a).
- A model failure makes the F4 job "failed"; F5 falls back to layer 1 (FR-13). A GitHub limit gives "Try again later" (UC-11 3b).
- Unique-key conflicts are normal answers, not errors: already marked, device reuse, second running job, second poll answer [P].

## 8. Configuration

- Parameter names and marks: SRS 3.4. Set on 22/11 [U22]: `QR_ROTATE_SEC` 10, `PHOTO_MAX_MB` 10, `LOAD_SIM_MARKS` 100 (initial values). The other OPEN values stay OPEN.
- Set on 21/11 and now in SRS 3.4 [U21]: `ATT_WINDOW_SEC` 300 and `SUBMIT_SEC` 60 (initial values, proposals); `LOGIN_ATTEMPT_LIMIT` 5; `LOGIN_LOCKOUT_SEC` 300, `LECTURER_SESSION_HOURS` 8 and `BROWSER_COOKIE_DAYS` 120 (names P). Decisions: D23-D28.
- Env vars, names only: `LECTURER_PASSWORD`, `SECRET_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `LLM_API_KEY`, `GITHUB_TOKEN` [SDD:107]; `BASE_URL`, `DB_PATH` [S1].
- The class location is a database setting, not an env var [U21].

## 9. Rejected alternatives

- Repository classes: rejected for KISS and length; they can be extracted later [U21].
- An ORM (SQLModel, SQLAlchemy); a frontend framework [U21].
- A queue system (Celery, Redis); synchronous F4 and F5 jobs [SDD, U21].
- Push with WebSockets [SDD].
- The login counter in the database; per-IP limits [U21].
- A GET that writes data, also for the Google callback [U21].
- QR state in server memory (the token is stateless) [SDD].
- The class location in env vars [U21].
- An LLM as the default head count; face recognition; a network (IP) check [U21, D2, D9].
- Backend-as-a-service [U21].

## 10. Tests

The strategy is in `stp.md` (TBD), with IDs `TC-nn` [D20]. Proposal: each service class is tested through its public methods on a temporary SQLite file with a set `Clock`; controllers through the FastAPI test client; `Google`, `PeopleCounter` and `LlmGateway` are replaced by fakes [P].

## 11. Check: FR-01 to FR-07

| FR | Classes | Tables | Sequence |
|---|---|---|---|
| FR-01 | RosterService | roster_entries | 4.1 (opt) |
| FR-02 | AttendanceService, QrTokens | class_sessions, class_location | 4.1 |
| FR-03 | StudentIdentity, RosterService, AttendanceService | devices, flags | 4.2 |
| FR-04 | AttendanceService, QrTokens, StudentIdentity | marks, flags, class_location | 4.3 |
| FR-05 | HeadCountService, PeopleCounter | head_counts | 4.4 |
| FR-06 | AttendanceService, RosterService | marks, roster_entries | 4.4 |
| FR-07 | AttendanceService | marks, roster_entries, flags | 4.4 |

F2-F5 in short: FR-08/09 CommentService, `comments`; FR-10/11 PollService, `polls`, `poll_answers`; FR-12 SummaryService, `summaries`, `jobs`, 4.5; FR-13/14/15/19/20 RepoReviewService and LlmGateway, `repo_results`, `jobs`, `checklist`, `f5_reports`; FR-16/18 controllers; FR-17 LecturerAccess (memory).

## 12. Open items

- S2: QR timing (`QR_ROTATE_SEC`, `SUBMIT_SEC`, `ATT_WINDOW_SEC`) and up to 100 simultaneous marks on one SQLite file. Not verified.
- S3: block or flag when out of range (FR-04). The "no class location set" rule is a proposal. **Risk:** laptop geolocation can be inaccurate when the lecturer uses "Use my current location" (not verified, test in S3).
- S4: the `PeopleCounter` implementation. S5, S6: the model provider and the F4 and F5 limits.
- Not verified: `segno`, the 120-day cookies, the WhatsApp in-app browser and the 100 test-user cap [S1].
