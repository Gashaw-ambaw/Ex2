# Project Plan – Ex2

Status: draft (stage 1). Last updated: 20/11/2026. Deadline: 25/11/2026.
Closed decisions are in `decisions.md`. Everything below is open or a working assumption.
Read first: `decisions.md`, `use_cases.md`, `sow.md`.

## 1. Goals (initial, to refine)

| Metric | Target |
|---|---|
| Speed | At least 95% of present students are marked within the 5-minute window |
| Plausibility | The lecturer is alerted when marks exceed the photo count by more than a tolerance (initial: 5%) |
| Lecturer effort | 3-4 actions per class (open, photo, close, export) |

## 2. Working assumptions (to verify in spikes)

- Marking happens once, at the end of the class, in a 5-minute window.
- The attendance QR rotates every 5-10 s. The code is time-based and stateless (secret on the server, current and previous window accepted). A student has about 60 s after scanning to submit.
- Each roster entry is marked once per class. The device is registered once; later classes are scan, confirm the name, one tap.
- Flags for the lecturer: several identities on one device, location out of range (block or flag: S3), count gap.
- Photo count counts people only, using a pre-trained model.
- Late students are added by the lecturer and labelled "manual".
- Expected load: up to 100 simultaneous marks (roster about 102).
- Sessions and marks are kept to the end of the semester; the photo is deleted after counting (D21).
- Stack candidates: Python with FastAPI or Flask, SQLite, a background job runner, one deployable app.

## 3. Open decisions

| # | Question | How we decide |
|---|---|---|
| 1 | Location: block or flag only | Spike S3 in the real hall |
| 2 | QR rotation and window timing | Measure with several phones |
| 3 | Count method and tolerance | Spike S4 on class photos with manual counts |
| 4 | Language, framework, hosting | Resolved: Python, FastAPI, SQLite; Railway (D23). Railway plan and budget OPEN |
| 5 | If Google sign-in fails on phones, what replaces it (SoW: the lecturer takes attendance the regular way; alternative: magic link by email, proposal, not approved) | Spike S1 |
| 6 | Export format (file, Google Sheets) | Resolved: a file, CSV or XLSX (FR-07); Google Sheets optional |
| 7 | F2 refresh interval and abuse handling | Resolved: `REFRESH_SEC` and `COMMENT_MIN_INTERVAL_SEC` (FR-08, FR-09) |
| 8 | F4 and F5 models, Hebrew support | Spikes S5, S6 |

## 4. Questions for the lecturer

- What is the demo date, and the exact submission time on 25/11?
- F5: is the report for the student, the lecturer, or both? Assumed both (D13). May the class's Ex1 repos be used?

## 5. Spikes (time-boxed, code in `spikes/`)

| # | Goal | When / status |
|---|---|---|
| S1 | Hosting with HTTPS on Android phones, cookies, Google sign-in in the WhatsApp in-app browser, test-user cap (about 100 vs roster about 102); hosting model (serverless or a small always-on server), long jobs (ffmpeg), SQLite persistence, fixed redirect URL | Done 21/11 (`results.md`): Railway; plan and budget OPEN |
| S2 | Time-based QR and up to 100 simultaneous marks | Before F1. Not started |
| S3 | Location (about 50 m) in the real hall, on a class day | On a class day (date not set). Not started |
| S4 | Head count on class photos against manual counts | Before F1 is finished. Not started |
| S5 | F4 summary from a Hebrew transcript | Before F4. Not started |
| S6 | F5 report on 2-3 repos | Before F5. Not started |

Also: a survey of existing tools (including NotebookLM) for the tools report.

## 6. Risks

| Risk | Mitigation |
|---|---|
| Google sign-in blocked in in-app browsers or by the user cap | Test early (S1); decide a replacement |
| Burst of marks on campus Wi-Fi | Load test, rehearse, stateless server |
| Indoor GPS inaccurate | Range of tens of meters; flag or block, decided in S3 |
| A student in the corridor marks without being in class | Known limit; the photo count shows the gap |
| Count model unreliable | Calibrate; alert only |
| Prompt injection through README text in F5 | Treat repo text as data, show aggregates only |
| Too little time for five features | Strict order, thin F4 and F5, buffer |

## 7. Schedule

| Date | Goal | Status |
|---|---|---|
| 18-19/11 | SoW. Repo documents brought up to date. Tools report. | SoW draft written; tools report not started |
| 19-20/11 | SRS draft, human review, SRS closed. SDD, EDD, test plan. | SRS and SDD drafts written; human review not verified; EDD and test plan not started |
| 21-22/11 | F1 end to end on real phones. | Planned |
| 23/11 | F2, F3. | Planned |
| 24/11 | F4 and F5 thin slices, README, results. | Planned |
| 25/11 | Final check and submission (hour to confirm). | Planned |

S3 happens on the next class day. A rehearsal with 5-10 friends is planned before submission; the in-class demo follows submission.