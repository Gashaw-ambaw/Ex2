# Test Plan

Status: draft (F1-F4). Date: 22/11/2026; F2-F3 added 26/11/2026; F4 added 28/11/2026. Read with `srs.md`, `use_cases.md` and `edd.md` (section 10). IDs follow D20.
F5 test cases are added when it is built; until then B11 (srs.md) is covered for F1-F4.

## 1. Strategy

- Services (`QrTokens`, `AttendanceService`, `RosterService`, `StudentIdentity`, `HeadCountService`, `CommentService`, `PollService`) are tested through their public methods, on a temporary SQLite file per test and a set `Clock`. `Google` and `PeopleCounter` are fakes [EDD:493]; only TC-68 loads the real model. The language model client is a fake in all tests.
- Controllers are thin: tested through the FastAPI test client, written after the code. Tests first only for classes with logic: `QrTokens`, the marking rules of `AttendanceService`, the count gap, `HeadCountService`, `CommentService` and `PollService` (TC-10 to TC-13, TC-21 to TC-26, TC-28 to TC-31, TC-47 to TC-51, TC-55 to TC-62, TC-65, TC-67, TC-68).
- Test data: `sample_data/` only (`roster.csv`: 102 students and 2 staff rows; `roster_bad.csv`; `roster_duplicates.csv`). No real data (D5, NFR-07).
- Phone tests are manual, on 2-3 Android phones with the deployed app. The load test (S2) runs on the real mark endpoint on a local server (one uvicorn worker, a SQLite file), not on Railway: the deployed app has no test route and no real test accounts.
- Parameter values are those of SRS 3.4: `ATT_WINDOW_SEC` 300, `QR_ROTATE_SEC` 10, `SUBMIT_SEC` 60, `GAP_TOLERANCE_PCT` 5, `PHOTO_MAX_MB` 10, `LOAD_SIM_MARKS` 100.

## 2. F1 test cases

| TC | FR | UC flow | Type | Expected result |
|---|---|---|---|---|
| TC-01 | FR-01 | UC-00 main | API | `roster.csv`: preview shows 104 rows; after removing the 2 staff rows and confirming, 102 active entries; only name and email are read (the groups column is ignored) |
| TC-02 | FR-01 | UC-00 2a | API | `roster_bad.csv` (no email column): the error names the column; nothing saved |
| TC-03 | FR-01 | UC-00 2b | API | `roster_duplicates.csv`: duplicate emails listed; nothing saved |
| TC-04 | FR-01 | UC-00 4a | unit | A new file replaces the roster, entries matched by lower-case email; missing ones become inactive; earlier marks keep their name |
| TC-05 | FR-02 | UC-01 main | API | Start class creates today's session; Open attendance shows a QR, a countdown and a live count of 0 |
| TC-06 | FR-02 | UC-01 1a | API | Open attendance with no session: "Start class first"; no window |
| TC-07 | FR-02 | UC-01 2a | manual | Lecturer page offline for 10 s, then online: the QR resumes |
| TC-08 | FR-02 | UC-01 4a | API | Close early: the next scan gets "Attendance is closed"; totals (marks, flags) shown |
| TC-09 | FR-02 | UC-01 main s4 | unit | Clock past `ATT_WINDOW_SEC`: the window is closed and no QR is valid |
| TC-10 | FR-02, FR-04 | UC-03 s2 | unit | `QrTokens`: a token of the current window is accepted |
| TC-11 | FR-04 | UC-03 s2 | unit | A token of the previous window is accepted |
| TC-12 | FR-04 | UC-03 2a | unit | A token older than the previous window is rejected ("scan again") |
| TC-13 | FR-04 | UC-03 s2 | unit | A token of another session is rejected |
| TC-14 | FR-03 | UC-02 main; UC-03 3a | API | Fake Google, Confirm registration: the browser is linked to the roster entry; "Hello name"; then the mark page opens if the scan is still valid |
| TC-15 | FR-03 | UC-02 1a | manual | Google sign-in in the WhatsApp in-app browser: the page says "Open in Chrome" (**not verified**) |
| TC-16 | FR-03 | UC-02 1b | API | The student cancels at Google: no registration |
| TC-17 | FR-03, FR-04 | UC-02 4a; UC-03 3b | API | An email not on the roster: "contact the lecturer"; no registration, no mark |
| TC-18 | FR-03 | UC-02 4b | unit | A browser linked to student A registers as B: it is linked to B; flag `relinked` |
| TC-19 | FR-03 | UC-02 4c | unit | A second device for the same student: added; flag `new_device` |
| TC-20 | FR-03 | UC-02 5a | API | The scan ticket is older than `SUBMIT_SEC` after sign-in: "scan again" |
| TC-21 | FR-04 | UC-03 main | unit | Registered device, valid ticket, open window: one mark, source `self`, only a yes/no location stored |
| TC-22 | FR-04 | UC-03 4a | unit | The tap comes after `SUBMIT_SEC`: rejected, "scan again" |
| TC-23 | FR-04 | UC-03 5a | unit | A second mark for the same roster entry: the earlier time is shown; still one row |
| TC-24 | FR-02, FR-04 | UC-03 5b | unit | The window is closed: "Attendance is closed; ask the lecturer."; no mark |
| TC-25 | FR-04 | UC-03 5c | unit | A device that marked A tries B: blocked; flag `device_reuse` on the entry of the student who tapped |
| TC-26 | FR-04 | UC-03 5d | unit | Location out of range or denied: mark recorded with a flag. No class location set: check skipped, warning on the lecturer page |
| TC-27 | FR-05 | UC-04 main | API | Fake counter returns 97 for 104 marks: alert "gap 7", flagged marks first; count and gap stored; photo deleted |
| TC-28 | FR-05 | UC-04 s4 | unit | Count gap: alert when marks > count x 1.05. 104 marks / 97: alert; 101 / 97: no alert; 102 / 97: alert |
| TC-29 | FR-05 | UC-04 1a | API | A file over `PHOTO_MAX_MB` or not an image: error; nothing stored |
| TC-30 | FR-05 | UC-04 2a | API | The counter fails: an error; no count stored; no alert |
| TC-31 | FR-05 | UC-04 4a | unit | Count higher than marks: no alert |
| TC-32 | FR-05, FR-06 | UC-04 4b; UC-05 3a | unit | A gap with no flagged mark: alert shown, the list is unchanged |
| TC-33 | FR-06 | UC-05 main s1-4 | API | The table shows name, time, source, flags, status; flagged rows first and highlighted; flags without a mark in one line; a mark can be set to unverified |
| TC-34 | FR-06 | UC-05 4a | API | An unverified mark is set back to normal |
| TC-35 | FR-06 | UC-05 main s5 | API | Add a mark by hand from the roster: a mark with source `manual` |
| TC-36 | FR-06 | UC-05 5a | API | Add a student not on the roster (name, email) first, then the mark |
| TC-37 | FR-06 | UC-05 5b | API | Add a student who already has a mark: a message; no second row |
| TC-38 | FR-06 | UC-05 5c | API | Edit a roster email: sign-in with the new email matches the entry |
| TC-39 | FR-06 | UC-05 5d | API | Reset removes only the mark; the entry stays and a mark can be added by hand |
| TC-40 | FR-07 | UC-05 s6 | API | Export: CSV, UTF-8 with BOM, columns name, email, time, source, status, flags; one row per mark |
| TC-41 | FR-07 | UC-05 6a | API | A forced export error: an error message; the table is unchanged |
| TC-42 | FR-17 | UC-00, 01, 04, 05 | API | Lecturer pages need the password; after `LOGIN_ATTEMPT_LIMIT` wrong attempts, login is locked for `LOGIN_LOCKOUT_SEC` |
| TC-43 | NFR-02, NFR-04 | F1 end to end | manual | 2-3 Android phones on the deployed app: register once, scan, one tap, review, export; the lecturer needs the 3-4 actions |
| TC-44 | NFR-03, NFR-05 | S2 | API (load) | `LOAD_SIM_MARKS` marks at once on the real endpoint: each roster entry is recorded once; the time to finish is noted |
| TC-45 | FR-02 | UC-01 1b (D31) | API | Open attendance when today's session already has a closed window: "Attendance already closed for this session"; no window is opened |
| TC-46 | FR-02 | UC-01 1b | API | After a closed or expired window, Start a new session (optional name) creates a second session for today; Open attendance works; the old session keeps its marks |
| TC-66 | FR-05 | UC-04 precondition | API | No class today: "Start class first"; window never opened or still open: "Close attendance first"; the form shows only after Close; the upload needs the password |
| TC-67 | FR-05 | UC-04 main (D38) | unit | A second photo of the same session replaces the count |
| TC-68 | FR-05 | UC-04 s2 | unit | The real model loads from `app/models/` and counts nobody in a black picture |

TC-08 and TC-09 run in two parts: the window side (state, close, expiry) in step 4; the scan side ("Attendance is closed", `check_scan`) in step 5.
TC-27 to TC-32 and TC-66 to TC-68 run with S4 (27/11); TC-38 ran in step 5.

## 3. F2-F4 test cases

| TC | FR | UC flow | Type | Expected result |
|---|---|---|---|---|
| TC-47 | FR-08 | UC-06 main | unit, API | A comment is stored with session, browser id and time, no identity; "Sent"; the browser sees only its own comments of today's session, newest first |
| TC-48 | FR-08 | UC-06 2a | API, manual | No session today: /c says "Class has not started"; a sent comment is not stored |
| TC-49 | FR-08 | UC-06 3a | unit, API | Empty, spaces only or over `COMMENT_MAX_CHARS`: "Write 1 to 300 characters."; the text is kept; nothing stored |
| TC-50 | FR-08 | UC-06 4a | unit | Same browser after 9 s: "Wait a moment."; after `COMMENT_MIN_INTERVAL_SEC` (10 s): stored |
| TC-51 | FR-08 | UC-06 4c | unit | After Close and after a new session, a comment goes to today's latest session; an earlier date is never used |
| TC-52 | FR-09 | UC-07 main | API | Comments page: the latest session (also from an earlier day), newest first; refresh every `REFRESH_SEC`; "Refresh now" |
| TC-53 | FR-17 | UC-07 1a; UC-08 | API | /comments, /comments/state, /class/link, /polls, /polls/state, /polls/start, /polls/close need the password |
| TC-54 | FR-09 | UC-07 2a | manual | Comments page offline: "Offline", then resumes |
| TC-55 | FR-10 | UC-08 main | unit | Start a poll (2-4 options, optional correct); answers counted; Close; votes per option and right/wrong |
| TC-56 | FR-10 | UC-08 1a | unit, API | Empty or spaces-only question, fewer than 2 or more than 4 options, correct on a blank field: "Write a question and 2 to 4 options."; nothing stored. Blank fields are dropped; the correct mark stays with its text |
| TC-57 | FR-10 | UC-08 2a | unit | Start while a poll is open (also one from an earlier day): the open poll is closed and its results kept |
| TC-58 | FR-10 | UC-08 3a | manual | Polls page offline while a poll is open: "Offline", then resumes |
| TC-59 | FR-10, FR-11 | UC-08 s6; UC-09 main | API | The student answers and sees "Thanks..."; after Close "Correct"/"Wrong" and the right answer; the lecturer sees votes, the correct answer and right/wrong |
| TC-60 | FR-11 | UC-09 2a | API | No poll: "No question now. Refresh when the lecturer announces one" |
| TC-61 | FR-11 | UC-09 3a | unit, API | A second answer of the same browser is not stored; "You answered" |
| TC-62 | FR-11 | UC-09 3b, s5 | unit, API | Closed before answering: the results are shown and an answer gets "Not accepted." (also a bad option, an old poll or an earlier session); without a correct option: the distribution |
| TC-63 | NFR-08, FR-16, FR-18 | UC-06, UC-09 | API | /c, /c/comment and /c/answer need no sign-in; the `anon` cookie is separate from the device cookie; comment and answer rows hold no device or roster id; /class/link shows `BASE_URL/c` |
| TC-64 | FR-10 | UC-08 precondition | API, manual | Start poll with no session today: "Start class first."; nothing stored |
| TC-65 | FR-10 | UC-08 s3 (D36) | unit, API | While a poll is open, /polls and /polls/state give only the number of answers: no votes per option, no correct answer |
| TC-69 | FR-12 | UC-10 s2-s4 | unit | A VTT becomes plain text; a txt is kept as is |
| TC-70 | FR-12 | UC-10 2a | unit, API | Wrong type, over 2 MB, not UTF-8 or no file: error, no job, nothing stored |
| TC-71 | FR-12 | UC-10 4c | unit | Empty or damaged transcript: error |
| TC-72 | FR-12, NFR-11 | UC-10 s3-s5 | unit | The job stores the summary; the model gets the text and the instruction (structure, 600 words, same language) |
| TC-73 | FR-12 | UC-10 4a | unit, API | Model error: "Failed: upload again.", nothing stored, no message or key in the log |
| TC-74 | FR-12 | UC-10 s3 | unit | A second upload while a job runs is refused |
| TC-75 | FR-12 | UC-10 s3 (D25) | unit, API | A running job of an earlier server run is shown as failed |
| TC-76 | FR-12, FR-17 | UC-10 precondition, s1, s6 | API | Password needed; no session; no key; Processing refresh; the latest session's summary |
| TC-77 | FR-12 | UC-10 s4 | unit | The model call (model, 4000 tokens, data apart from instructions), token log, refusal or cut-off or empty fails, key stripped |
| TC-78 | FR-12, FR-17 | UC-10 s7 | API | The download needs the password |
| TC-79 | FR-12 | UC-10 s7 | API | No session or no summary: 404 "No summary yet." |
| TC-80 | FR-12, NFR-11 | UC-10 s7 | API | The file is the stored text (Hebrew too), UTF-8, ASCII name with the session date |
| TC-81 | FR-12 | UC-10 s6-s7 | API | The download button shows only when a summary exists |
| TC-82 | FR-12 | UC-10 s6 | unit, API | A short line without end punctuation is shown as a title; the text stays escaped |

## 4. B11 coverage: alternative flows of UC-00 to UC-10 (56)

| UC | Flow | TC |
|---|---|---|
| UC-00 | 2a | TC-02 |
| UC-00 | 2b | TC-03 |
| UC-00 | 4a | TC-04 |
| UC-01 | 1a | TC-06 |
| UC-01 | 1b | TC-45, TC-46 |
| UC-01 | 2a | TC-07 |
| UC-01 | 4a | TC-08 |
| UC-02 | 1a | TC-15 |
| UC-02 | 1b | TC-16 |
| UC-02 | 4a | TC-17 |
| UC-02 | 4b | TC-18 |
| UC-02 | 4c | TC-19 |
| UC-02 | 5a | TC-20 |
| UC-03 | 2a | TC-12 |
| UC-03 | 3a | TC-14 |
| UC-03 | 3b | TC-17 |
| UC-03 | 4a | TC-22 |
| UC-03 | 5a | TC-23 |
| UC-03 | 5b | TC-24 |
| UC-03 | 5c | TC-25 |
| UC-03 | 5d | TC-26 |
| UC-04 | 1a | TC-29 |
| UC-04 | 2a | TC-30 |
| UC-04 | 4a | TC-31 |
| UC-04 | 4b | TC-32 |
| UC-05 | 3a | TC-32 |
| UC-05 | 4a | TC-34 |
| UC-05 | 5a | TC-36 |
| UC-05 | 5b | TC-37 |
| UC-05 | 5c | TC-38 |
| UC-05 | 5d | TC-39 |
| UC-05 | 6a | TC-41 |
| UC-06 | 2a | TC-48 |
| UC-06 | 3a | TC-49 |
| UC-06 | 4a | TC-50 |
| UC-06 | 4b | Could (srs App. C), not built |
| UC-06 | 4c | TC-51 |
| UC-07 | 1a | TC-53 |
| UC-07 | 2a | TC-54 |
| UC-07 | 4a | Could (srs App. C), not built |
| UC-07 | 4b | Could (srs App. C), not built |
| UC-07 | 4c | Could (srs App. C), not built |
| UC-08 | 1a | TC-56 |
| UC-08 | 2a | TC-57 |
| UC-08 | 3a | TC-58 |
| UC-08 | 6a | Could (srs App. C), not built |
| UC-09 | 2a | TC-60 |
| UC-09 | 3a | TC-61 |
| UC-09 | 3b | TC-62 |
| UC-09 | 3c | Could (srs App. C), not built |
| UC-10 | 2a | TC-70 |
| UC-10 | 4a | TC-73 (the Retry button is Could, not built) |
| UC-10 | 4b | Could (srs App. C), not built |
| UC-10 | 4c | TC-71 |
| UC-10 | 4d | Could (srs App. C), not built |
| UC-10 | 6a | Could (srs App. C), not built |

56 of 56 flows of UC-00 to UC-10 are listed: 47 have a TC, 9 are Could (srs App. C), not built (D35). The 17 flows of UC-11 to UC-13 are added when those features are built.
