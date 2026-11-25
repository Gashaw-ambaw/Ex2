# AI Usage

Tools: Claude (chat – planning, analysis, drafting), Claude Code (reads the repo; edits files only after I approve its plan).
Working rule: AI proposes and drafts; I decide. Claude Code runs git only when I ask for it in that message (CLAUDE.md rule 3).
Real roster and class photos were shown only in the planning chat to understand their structure; they are not in this repo.

| Date | Tool | What AI did | What I did |
|---|---|---|---|
| until 14/11 | Claude | Assignment analysis, repo skeleton plan, README and CLAUDE.md drafts, attendance anti-cheat discussion | Defined scope, created repo, edited and committed |
| 14/11 | Claude | project_plan.md draft | Reviewed, committed |
| 14/11 | Claude Code | Read-only check of repo vs assignment (inconsistencies, gaps) | Chose which findings to apply |
| 15–16/11 | Claude | Update after Zoom left scope; README, decisions, AI usage rewrite; next-steps analysis | Decided, edited, committed |
| 17/11 | Claude | Lecture transcript analysis | Chose which findings to apply |
| 17–18/11 | Claude | Decisions D16-D20; use cases (use_cases.md) | Decided options, reviewed and edited |
| 18/11 | Claude | SRS and SoW planning; SoW drafting and review | Decided scope, acceptance criteria and cut order; copied the text |
| 18/11 | Claude Code, Claude | Comparison of a Claude Code plan with a Claude outline for the SoW | Chose which findings to apply |
| 18/11 | Claude Code | Read-only repo inventory and analysis; D9 change (location only, no network check) | Decided D9; approved the edits |
| 18/11 | Claude Code | SRS draft (FR-01..FR-20, NFR-01..NFR-12), written in plan mode | DRAFT, to edit: approved the plan; review of the SRS text later |
| 19/11 | Claude Code | Consistency fixes after the SRS: UC-05 5d, UC-08 step 3, sow.md F5 acceptance, D22, SRS notes | Decided which fixes, approved the edits |
| 20/11 | Claude Code | SDD outline review, revised plan and draft; SRS wording (lecturer device, Android only) | Decided the open points, approved the edits |
| 21/11 | Claude Code | S1 spike in `spikes/s1/`: Hello page, cookie test, Google sign-in test, SQLite write test (FastAPI); local runs with dummy settings; code comments; Railway docs check | Chose the stack and host (Railway Trial); ran the Railway, phone and Google tests; edited and committed |
| 21/11 | Claude Code | EDD plan in three rounds (conflict check of SRS, SDD and use cases against my answers); EDD draft (`docs/edd.md`): class and sequence diagrams, schema, cookies, doc-fix list | Decided the stack details, sessions, cookies, class location and scope; approved the plan; review of the EDD text later |
| 21/11 | Claude Code | Doc fixes after the EDD in SRS, SDD, use cases, decisions and project plan (Start class, class location, 60 s submit, 5-minute window, login lockout, cookie and session constants, alternative-flow recount); new decisions D23-D28 drafted from my answers | Approved the list with changes; chose the D19 wording and the UC-06 rule; review of the decision texts later |
| 22/11 | Claude Code | F1 start: deadline fix, parameter values, D23 (Railway Hobby), code layout, rehearsal, UC-02 1a | Answered the 21 items and the open questions; approved the edits |
| 22/11 | Claude Code | Synthetic roster files in `sample_data/` (102 fake students, bad and duplicate files) | Specified headers and counts; no real data |
| 22/11 | Claude Code | D30-D31 propagation (FR-01, FR-02, UC-00, D19, EDD 4.1 note) and TC-45 | Approved the edits and the closed-window message |
| 24/11 | Claude Code | F1 step 1: `app/` skeleton (Settings, Db with 15 tables, Clock, /health, Google client), 26 tests, requirements; code comments | Approved the plan; ran the Railway steps; review of the code later |
| 24/11 | Claude Code | F1 step 2: `QrTokens` (`app/qr_tokens.py`), 9 tests written first (TC-10..13 + 5 extra); deadline 30/11 and schedule edits in the documents | Approved the plan and the edits; review of the code later |
| 24/11 | Claude Code | F1 step 3: `RosterService`, `LecturerAccess`, login and roster pages (`app/templates/`), 39 tests written first; D32, D30 header names, EDD 2.1 edits | Approved the plan and the answers Q1-Q3; chose the D32 text; review of the code later |
| 24/11 | Claude Code | F1 step 4: `AttendanceService` (Start class, class location, 300 s window), class page and QR page (`segno`), 60 tests written first; EDD and STP lines | Approved the plan and the 7 answers; review of the code later |
| 25/11 | Claude Code | F1 step 4b: `new_session` (UC-01 1b) and the "Start a new session" button, 16 tests written first; D31 changed to built; doc edits | Found the expired-window problem and approved the fix; approved the plan and the answers |
| 25/11 | Claude Code | F1 step 5: `StudentIdentity` (Google sign-in, device link, flags), minimal `/scan`, `check_scan`, `add_flags`, roster `add_entry` and `edit_email` with forms, 79 tests written first (fake Google) | Approved the plan and the answers Q1-Q6; review of the code later |
| 22/11 | Claude Code | STP draft (F1): strategy, 44 test cases, B11 table for the 32 F1 flows | Approved the plan; review of the STP text later |
