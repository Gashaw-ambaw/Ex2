# S1 results (21/11/2026)

Source: my test runs. Screenshots for steps 1-6a, my report for the rest.

## Tested

- Stack: Python 3.13 + FastAPI + uvicorn, one worker (one "Started server process" in the deploy log). Code: `spikes/s1/main.py`.
- Host: Railway Trial, always-on (Serverless off), fixed HTTPS URL, Volume at `/data`. Railpack 0.43.0 chose Python 3.13.18 and the uvicorn start command by itself.

## Worked

- Hello page over HTTPS on an Android phone (POCO X7 Pro, Chrome 157) and a tablet, Wi-Fi and mobile data. Load under 1 second, also after 10+ minutes idle.
- Cookie kept after reload and after closing and reopening the tab (laptop, tablet).
- Google sign-in on computer and phone (Chrome): sign-in, refresh, close/reopen, sign-out. A second Google account, not on the Test users list, also signed in (checked by me).
- SQLite on the Volume: 18 rows survived a Redeploy and a new deployment.
- 90 s background job (DB row + thread, same process): finished with the tab closed and no traffic. A double start gave one job. A Redeploy mid-job gave "failed, server restarted", and a new job could start after.

## Problems

- The Google client secret gave `invalid_client` until a new one was created.
- Railway "Redeploy" runs the old commit. Use "Deploy latest commit".
- A GET route that writes data produced duplicate rows (probably browser preload, not verified). State-changing actions must be POST.

## Not verified

- WhatsApp in-app browser sign-in (the test phone opens Chrome).
- 24-hour cookie lifetime.
- Sleep after hours without traffic (only 10 minutes tested).
- The 100 test-user cap (one extra account tested).
- Google OAuth app: Publishing status was not checked in Google Cloud Console (Audience). The 100 test-user cap applies only in Testing mode (not verified), so the result of the extra-account test depends on it.
- Concurrent writes (S2).
- Railway Trial limits and cost.

## Open (my decision)

- Railway Hobby or Render paid, and the budget. Python + FastAPI + SQLite stays a candidate stack until I approve it.

## F1 live checks (25/11/2026)

- MEASURED [TC-05] After login the app lands on /class; Open attendance shows the QR page; the countdown ran from 300 s; the QR changed about every 10 s.
- MEASURED [no TC; D28] "Use my current location" saved the class location, and the warning disappeared.
- MEASURED [TC-45] Close, then Open again: "Attendance already closed for this session".
- MEASURED [no TC; UC-03 s1] A phone camera scanned the QR and opened /scan?s=..&w=..&t=.. (a 404 before step 5).
- MEASURED [TC-46] After an expired window, "Start a new session" (name "Test") created a second session for today; Open attendance worked, the countdown started at 300 s; the button was not shown while the window was open.
- MEASURED [TC-14] On a laptop and two real phones: tester A registered with Google sign-in; the second scan went straight to "Hello" without Google.
- MEASURED [TC-17] Tester B, not on the roster, got "Contact the lecturer"; after the roster form added B, B registered.
- MEASURED [TC-20] More than 60 s on the Google account screen gave "Registered. Scan again."
- MEASURED [TC-19] After clearing the site data and registering again, the class page showed Flags: 1 (new_device).
- NOT VERIFIED: scan from about 3 m on a projector; the Wi-Fi off and on check [TC-07] (I did not report it); opening the scan link inside WhatsApp [TC-15]; the 120-day cookie; the 100 test-user cap; real class location in the hall (S3); iPhone.

## F1 live checks (26/11/2026)

Setup: a laptop, two phones (A and B) and a third account (tester C).

- MEASURED [TC-21] One self mark with location allowed worked.
- MEASURED [TC-23] A second scan showed "Already marked at" with the same time.
- MEASURED [TC-22] A ticket older than 60 s gave "Scan the QR again."
- MEASURED [TC-26] B, with location blocked, was marked, and the flag count went up.
- MEASURED [TC-25] A's phone, relinked to C, was blocked with "This phone already marked another student in this class. Ask the lecturer."; the mark count did not change.
- MEASURED [UC-03 5b] After Close, B got "Attendance is closed; ask the lecturer."
- MEASURED [no TC] A was relinked back. Final totals in the last session: Marks 2, Flags 3 (relinked, device_reuse and one more, probably location from B; the page shows only the number).
- NOT VERIFIED: the kind of each flag; location in the real hall (S3); iPhone; WhatsApp.

## F1 live checks, step 7 (26/11/2026)

- MEASURED [TC-33] /class/review: flagged rows first and highlighted; flag kinds seen: location, relinked, device_reuse. The "Flags without a mark" line showed one name, each kind once.
- MEASURED [TC-33, TC-34, TC-35, TC-39] Unverified and back to Normal, Add a mark by hand (source manual) and Reset worked.
- MEASURED [TC-40] Export CSV opened in Excel with the six columns, one row per mark. "####" in the time column was only a narrow Excel column.
- MEASURED [TC-42] After Logout, /class/review redirected to /login.
- MEASURED [no TC] A first check showed the location flag on the wrong phone. A repeat with two different Google accounts and a new session showed it correctly. Probable cause: the two phones used one Google account (not proven).
- NOT VERIFIED: Hebrew names in the exported CSV.

## S2 load check (26/11/2026)

Setup: local server on my laptop (one uvicorn worker, a SQLite file), not Railway, because the deployed app has no test route and no real test accounts. Test: `tests/test_load.py`, synthetic students from `sample_data/`.

- MEASURED [TC-44] 100 marks sent at once: all replied "Marked at", each student recorded once (100 students, 100 devices); the last reply came after 2.8 s (limit 60 s).
- NOT VERIFIED: Railway CPU; campus Wi-Fi; NFR-03 (95% of students marked within the window); QR timing under load.

## F1 rehearsal (26/11/2026)

Setup: the deployed app, testers A and B, two Android phones with Chrome, different Google accounts.

- MEASURED [TC-43] Round 1 (session "Rehearsal"): A and B scanned, signed in with Google once, confirmed, tapped "I'm here" and got "Marked at". Review showed 2 marks, status normal, each with the flags location and new_device; new_device likely because the accounts already had a linked device from earlier checks (not verified).
- MEASURED [TC-43, NFR-02] Round 2 (session "Rehearsal 2"): one tap, no Google; about 10 s from scan to "Marked at" (rough, by me). Review showed 2 marks; A had no flag, B had location only. No errors, no help needed.
- MEASURED [TC-43, NFR-04] Lecturer actions (Open attendance, Close, Review, Export CSV): 4 actions without the class photo; with the S4 photo it would be 5 if Review counts, above the 3-4 target. Whether Review counts is an open decision (until S4). "Start a new session", tapped before opening, is not counted.
- MEASURED [TC-40] The exported CSV had English headers and English names.
- NOT VERIFIED: the lecturer action count with the class photo (S4); Hebrew names in the CSV; iPhone; real class location in the hall (S3).

## F2 live check (26/11/2026)

Setup: the deployed app, a laptop and two Android devices: a phone (A) and a tablet (B).

- MEASURED [TC-63] The Class link page showed the fixed QR and the text https://ex2-production.up.railway.app/c; A and B reached /c without sign-in.
- MEASURED [TC-47, TC-49, TC-50] "Sent"; a second send at once gave "Wait a moment" with the text kept; a Hebrew comment was accepted; a spaces-only comment gave the error.
- MEASURED [TC-52, TC-54] The Comments page showed the comments newest first; "Refresh now" worked; with the laptop Wi-Fi off it showed "Offline" and then resumed.
- MEASURED [TC-51] After the attendance window was closed, a new comment arrived at the top of the Comments page.
- PENDING 27/11 [TC-48] /c before Start class ("Class has not started"): today already had a session.

## F3 live check (26/11/2026)

Setup: as in the F2 live check.

- MEASURED [TC-65, TC-61] While open, the laptop showed "2 answered" and no per-option counts; A got "Thanks..." after answering and "You answered" when opening /c again.
- MEASURED [TC-58] "Offline" while open, then resumed.
- MEASURED [TC-59] After Close: votes per option, "(Correct answer)", "Right: 1. Wrong: 1."; A and B saw Correct or Wrong with the right answer.
- MEASURED [TC-62] A poll without a correct option: A and B saw the distribution.
- MEASURED [TC-57] Start while a poll was open: the new poll started with no error (the first poll is no longer open).
- MEASURED [TC-56] Empty question: "Write a question and 2 to 4 options."; the open poll stayed open.
- PENDING 27/11 [TC-64] Start poll before Start class ("Start class first.").
- NOT VERIFIED: iPhone; many students at once.

## F2-F3 known limits

- A refused Start poll clears the form.
- Refreshing /c?answered=1 shows "Thanks..." again; opening /c shows "You answered".
- If a new poll is started in a second /polls tab, the first tab keeps the old question while its count follows the new poll, until a reload.
- When the 8 h lecturer login expires while Comments or Polls is open, the page shows "Offline" instead of the login page.
- A poll left open in an earlier session of the same day is not shown on /polls; the next Start closes it.
- Clearing cookies, blocked cookies or a second browser get past the 10 s limit and the one-answer rule (use_cases.md Known limits 3-4).
- Not built: the Could flows (D35: retry of an unsent comment or answer; hide, show, delete comments; delete a poll); a private lecturer view of per-option counts while open; older sessions on the lecturer pages; poll history; editing a poll; a word filter.

## F1 known limits

- After a new session is started (UC-01 1b), review and export show the latest session only. A lecturer who starts a new session by mistake does not see the first session's marks there.
- The class page shows only the number of flags, not their kinds; the review page (/class/review) shows them.
- If a student once chooses "never allow" for location, the browser does not ask again, so every later mark of that device gets a location flag. The site cannot re-ask. Accepted for now (flags matter only when the D18 gap alert fires); a hint line for the student may be added later if time remains.
- The CSV export does not escape a value that starts with `=`, `+`, `-` or `@`, so a spreadsheet program could read it as a formula. Accepted for now (fix only if time remains).
- Adding a mark by hand does not check that the roster entry is active; only the picker leaves out inactive entries. Accepted for now.
- Hebrew names in the exported CSV were not tested (the file is UTF-8 with BOM).
- A scan does not keep a private window: the phone camera opens the link in the default browser (seen in the rehearsal, 26/11).
