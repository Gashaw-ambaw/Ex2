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
| 22/11 | Claude Code | STP draft (F1): strategy, 44 test cases, B11 table for the 32 F1 flows | Approved the plan; review of the STP text later |
