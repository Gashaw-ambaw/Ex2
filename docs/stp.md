# Test Plan

Status: draft (F1 only). Date: 22/11/2026. Read with `srs.md`, `use_cases.md` and `edd.md` (section 10). IDs follow D20.
F2-F5 test cases are added when those features are built; until then B11 (srs.md) is covered for F1 only.

## 1. Strategy

- Services (`QrTokens`, `AttendanceService`, `RosterService`, `StudentIdentity`, `HeadCountService`) are tested through their public methods, on a temporary SQLite file per test and a set `Clock`. `Google` and `PeopleCounter` are fakes [EDD:493].
- Controllers are thin: tested through the FastAPI test client, written after the code. Tests first only for classes with logic: `QrTokens`, the marking rules of `AttendanceService` and the count gap (TC-10 to TC-13, TC-21 to TC-26, TC-28).
- Test data: `sample_data/` only (`roster.csv`: 102 students and 2 staff rows; `roster_bad.csv`; `roster_duplicates.csv`). No real data (D5, NFR-07).
- Phone tests are manual, on 2-3 Android phones with the deployed app. The load test (S2) runs on the real mark endpoint.
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
| TC-24 | FR-02, FR-04 | UC-03 5b | unit | The window is closed: "Attendance is closed"; no mark |
| TC-25 | FR-04 | UC-03 5c | unit | A device that marked A tries B: blocked; flag `device_reuse` |
| TC-26 | FR-04 | UC-03 5d | unit | Location out of range or denied: mark recorded with a flag. No class location set: check skipped, warning on the lecturer page |
| TC-27 | FR-05 | UC-04 main | API | Fake counter returns 97 for 104 marks: alert "gap 7", flagged marks first; count and gap stored; photo deleted |
| TC-28 | FR-05 | UC-04 s4 | unit | Count gap: alert when marks > count x 1.05. 104 marks / 97: alert; 101 / 97: no alert; 102 / 97: alert |
| TC-29 | FR-05 | UC-04 1a | API | A file over `PHOTO_MAX_MB` or not an image: error; nothing stored |
| TC-30 | FR-05 | UC-04 2a | API | The counter fails: a form to type the count; the typed count gives the same alert rule |
| TC-31 | FR-05 | UC-04 4a | unit | Count higher than marks: no alert |
| TC-32 | FR-05, FR-06 | UC-04 4b; UC-05 3a | unit | A gap with no flagged mark: alert shown, the list is unchanged |
| TC-33 | FR-06 | UC-05 main s1-4 | API | The table shows name, time, source, flags, status; flagged first when the alert fired; a mark can be set to unverified |
| TC-34 | FR-06 | UC-05 4a | API | An unverified mark is set back to normal |
| TC-35 | FR-06 | UC-05 main s5 | API | Add a late student from the roster: a mark with source `manual` |
| TC-36 | FR-06 | UC-05 5a | API | Add a student not on the roster (name, email) first, then the mark |
| TC-37 | FR-06 | UC-05 5b | API | Add a student who already has a mark: a message; no second row |
| TC-38 | FR-06 | UC-05 5c | API | Edit a roster email: sign-in with the new email matches the entry |
| TC-39 | FR-06 | UC-05 5d | API | Reset removes only the mark; the entry stays and a mark can be added by hand |
| TC-40 | FR-07 | UC-05 s6 | API | Export: CSV, UTF-8 with BOM, columns name, email, time, source, status, flags; one row per mark |
| TC-41 | FR-07 | UC-05 6a | API | A forced export error: an error message; the table is unchanged |
| TC-42 | FR-17 | UC-00, 01, 04, 05 | API | Lecturer pages need the password; after `LOGIN_ATTEMPT_LIMIT` wrong attempts, login is locked for `LOGIN_LOCKOUT_SEC` |
| TC-43 | NFR-02, NFR-04 | F1 end to end | manual | 2-3 Android phones on the deployed app: register once, scan, one tap, review, export; the lecturer needs the 3-4 actions |
| TC-44 | NFR-03, NFR-05 | S2 | API (load) | `LOAD_SIM_MARKS` marks at once on the real endpoint: each roster entry is recorded once; the time to finish is noted |

## 3. B11 coverage: F1 alternative flows (32)

| UC | Flow | TC |
|---|---|---|
| UC-00 | 2a | TC-02 |
| UC-00 | 2b | TC-03 |
| UC-00 | 4a | TC-04 |
| UC-01 | 1a | TC-06 |
| UC-01 | 1b | **not tested**: deferred, not built (decided 22/11); if built, add a TC |
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

31 of 32 flows have a TC; 1 is "not tested" (UC-01 1b). The 41 flows of UC-06 to UC-13 are added when those features are built.
