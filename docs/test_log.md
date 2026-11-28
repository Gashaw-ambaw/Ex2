# Test log

Every check that was run, by date: spikes, live checks, the load check and the rehearsal, with the known limits found. The summary is in [results.md](results.md).
MEASURED = seen in a real run; NOT VERIFIED = not checked.

## S1 results (21/11/2026)

Source: my test runs. Screenshots for steps 1-6a, my report for the rest.

### Tested

- Stack: Python 3.13 + FastAPI + uvicorn, one worker (one "Started server process" in the deploy log). Code: `spikes/s1/main.py`.
- Host: Railway Trial, always-on (Serverless off), fixed HTTPS URL, Volume at `/data`. Railpack 0.43.0 chose Python 3.13.18 and the uvicorn start command by itself.

### Worked

- Hello page over HTTPS on an Android phone (POCO X7 Pro, Chrome 157) and a tablet, Wi-Fi and mobile data. Load under 1 second, also after 10+ minutes idle.
- Cookie kept after reload and after closing and reopening the tab (laptop, tablet).
- Google sign-in on computer and phone (Chrome): sign-in, refresh, close/reopen, sign-out. A second Google account, not on the Test users list, also signed in (checked by me).
- SQLite on the Volume: 18 rows survived a Redeploy and a new deployment.
- 90 s background job (DB row + thread, same process): finished with the tab closed and no traffic. A double start gave one job. A Redeploy mid-job gave "failed, server restarted", and a new job could start after.

### Problems

- The Google client secret gave `invalid_client` until a new one was created.
- Railway "Redeploy" runs the old commit. Use "Deploy latest commit".
- A GET route that writes data produced duplicate rows (probably browser preload, not verified). State-changing actions must be POST.

### Not verified

- WhatsApp in-app browser sign-in (the test phone opens Chrome).
- 24-hour cookie lifetime.
- Sleep after hours without traffic (only 10 minutes tested).
- The 100 test-user cap (one extra account tested). It applies only in Testing mode (not verified); the Publishing status (Google Cloud Console, Audience) was not checked, so the extra-account result depends on it.
- Concurrent writes (S2).
- Railway Trial limits and cost.

### Open (my decision)

- Closed 26/11: Railway Trial kept for submission and demo; recorded in decisions.md (D23).

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
- NOT VERIFIED: scan from about 3 m on a projector; the Wi-Fi off and on check [TC-07] (I did not report it); opening the scan link inside WhatsApp [TC-15]; the 120-day cookie; real class location in the hall (S3); iPhone.

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
- MEASURED [TC-48] 27/11/2026, before any Start class that day: /c without sign-in showed "Class has not started." (the laptop, in the Claude Desktop built-in browser, and a phone).

## F3 live check (26/11/2026)

Setup: as in the F2 live check.

- MEASURED [TC-65, TC-61] While open, the laptop showed "2 answered" and no per-option counts; A got "Thanks..." after answering and "You answered" when opening /c again.
- MEASURED [TC-58] "Offline" while open, then resumed.
- MEASURED [TC-59] After Close: votes per option, "(Correct answer)", "Right: 1. Wrong: 1."; A and B saw Correct or Wrong with the right answer.
- MEASURED [TC-62] A poll without a correct option: A and B saw the distribution.
- MEASURED [TC-57] Start while a poll was open: the new poll started with no error (the first poll is no longer open).
- MEASURED [TC-56] Empty question: "Write a question and 2 to 4 options."; the open poll stayed open.
- MEASURED [TC-64] 27/11/2026, before any Start class that day: Start poll returned "Start class first." (status 400); nothing was stored (the Polls page still showed the closed poll of the 26/11 session).
- NOT VERIFIED: iPhone; many students at once.

## S4 spike (27/11/2026)

Setup: my laptop; OpenCV 4.14.0.94 (headless); YOLOX-s ONNX from OpenCV Zoo (35.9 MB, Apache-2.0); 11 own photos, not committed. Manual counts by me, uncertainty ±1 (p34 ±2). Signed error = model - manual.

- MEASURED First run (downloaded code, RGB, score 0.5), 5 photos: counts 4, 5, 5, 4, 6 for 38, 29, 42, 24, 37; 0 of 5 within 10%; 0.42-0.83 s, about 302 MB.
- MEASURED Cause: the downloaded post-processing gave the duplicate filter (NMS) corner boxes instead of x, y, width, height; the current OpenCV Zoo file has the fix. Fix alone: counts 10, 10, 7, 7, 10; still 0 of 5.
- Fallback setup: fix, BGR input (as in the official YOLOX preprocessing), score 0.03.
- Tiling setup (chosen): fix, BGR, full photo plus 3x2 tiles, overlap 0.2, score 0.2, NMS 0.4. The best of 48 settings on the 5 tuning photos.

Tuning photos (settings chosen on these):

| Photo | Manual | Fallback | Error | % | s | MB | Tiling | Error | % | s | MB |
|---|---|---|---|---|---|---|---|---|---|---|---|
| p1 | 38 | 33 | -5 | -13.2 | 0.91 | 302 | 38 | 0 | 0 | 3.45 | 312 |
| p15 | 29 | 32 | +3 | +10.3 | 0.84 | 302 | 29 | 0 | 0 | 3.40 | 312 |
| p32 | 42 | 39 | -3 | -7.1 | 0.82 | 302 | 46 | +4 | +9.5 | 3.40 | 312 |
| p3 | 24 | 29 | +5 | +20.8 | 0.73 | 301 | 25 | +1 | +4.2 | 3.39 | 312 |
| p23 | 37 | 37 | 0 | 0 | 0.69 | 301 | 37 | 0 | 0 | 3.37 | 312 |

Held-out photos (one frozen run):

| Photo | Manual | Fallback | Error | % | s | MB | Tiling | Error | % | s | MB |
|---|---|---|---|---|---|---|---|---|---|---|---|
| p34 | 46 | 42 | -4 | -8.7 | 0.32 | 302 | 48 | +2 | +4.3 | 1.69 | 312 |
| p2 | 38 | 35 | -3 | -7.9 | 0.31 | 302 | 40 | +2 | +5.3 | 3.31 | 312 |
| p11 | 44 | 43 | -1 | -2.3 | 0.32 | 302 | 44 | 0 | 0 | 3.38 | 312 |

Final check (one frozen run):

| Photo | Manual | Fallback | Error | % | s | MB | Tiling | Error | % | s | MB |
|---|---|---|---|---|---|---|---|---|---|---|---|
| p13 | 29 | 28 | -1 | -3.4 | 0.55 | 301 | 28 | -1 | -3.4 | 1.65 | 312 |
| p14 | 41 | 43 | +2 | +4.9 | 0.55 | 301 | 45 | +4 | +9.8 | 1.74 | 312 |
| p21 | 41 | 49 | +8 | +19.5 | 0.52 | 301 | 42 | +1 | +2.4 | 3.41 | 312 |

Times are the median of 3 runs without model loading (0.13-0.41 s more); memory is the peak.

| 11 photos | Fallback | Tiling |
|---|---|---|
| Within 10% | 7 of 11 | 11 of 11 |
| Mean absolute error | 8.9% | 3.5% |
| Mean signed error | +1.2% (+0.1 people) | +2.9% (+1.2 people) |
| False alerts at 5% / 10% (computed: marks = manual count) | 4 / 1 | 0 / 0 |

- MEASURED The counter in the app gave the same count as the tiling script on 11 of 11 photos; 3.35-6.81 s per photo.
- Rejected: `supervision` 0.32.3 and `sahi` 0.14.1 (both MIT) need more libraries (for example matplotlib; supervision also scipy and av; sahi also shapely and the non-headless OpenCV). The tiling is our own code. YOLOX-m was not tried (101 MB).
- NOT VERIFIED: other halls and larger classes; p14 is borderline (9.8%; 12.5% if the true count is 40); slight over-counting (at 5% up to 6 extra marks could pass unnoticed, computed from p32 and p14).

## S4 live check (28/11/2026)

Setup: the deployed app on Railway.

- MEASURED [TC-66] An upload before Start class and before Close gave an error.
- MEASURED [TC-29] A file that is not an image gave an error. An 11 MB file was rejected; the upload from the browser took about 41 s.
- MEASURED [TC-27] A blank image was counted in 1.9 s: "No gap".
- MEASURED [TC-32] With 1 mark added by hand: "Marks 1, counted 0, gap 1. Check the flagged marks first."
- Approximate (read from the Railway graph): memory about 365 MB after the first count. Usage: $0.20 of the $5 credit; Trial stays.
- MEASURED [TC-27] A real photo (p3, my count 24 ±1; one of the tuning photos) with 30 hand marks of test roster students: "Marks 30, counted 25, gap 5. Check the flagged marks first." Same count as the spike. Time: under 1 s by my eye, not a measurement.
- Approximate (read from the Railway pages, about 11:55): memory about 425-430 MB after several counts (Metrics graph); one short CPU spike at the time of a count, well under 0.1 vCPU; top bar "24 days or $4.79 left" (Trial); Usage page $0.20 used of $5; the Trial plan section of the Usage page shows a 1 GB RAM limit.
- NOT VERIFIED: other halls; a photo taken and uploaded from a phone camera; "Counting failed" on the live site (TC-30 only).

## F4 live check (28/11/2026)

Setup: the deployed app on Railway, with the first instruction (at most 200 words, `max_tokens` 2000).

- MEASURED [TC-72] English sample: input 379 tokens, output 234.
- The wait I saw was 21 s: an upper bound, because the page refreshes every 20 s.
- Approximate (Console): $0.02 of $5 used so far.
- [TC-71] An empty VTT shows "The transcript is empty or damaged."
- Judged by me: the real Hebrew summary was mostly correct and fixed Zoom recognition errors from context; it missed a minor topic (the poll) and added one small inference. Because of this the summary was made longer and structured (D39).

Second check, same day, after the longer and structured instruction (600 words, `max_tokens` 4000):

- `/health` returned ok after the deploy.
- MEASURED [TC-72] A real Hebrew lecture of 45 minutes: input 4527 tokens, output 1495, stop reason `end_turn` (not cut off).
- ESTIMATE About 380 words, under the 600 ceiling.
- Approximate (Console): about $0.02 for this file.
- Judged by me: the length is very good.
- The summary has a recap and topics with titles, and now includes the poll topic.
- The file chooser did not offer a PDF. The server's refusal of a PDF is NOT VERIFIED on the live site (TC-70 only).
- NOT VERIFIED: a longer lecture (1.5 to 3 hours).

Third check, same day, after the download and the titles:

- [TC-80] The downloaded .txt file was correct (judged by me).
- [TC-81, TC-82] The titles and the "Download .txt" button next to "Summarize" worked on the live site (judged by me).
- Judged by me: the second summary added nothing that was not said.

## F4 known limits
- The download gives only the latest summary of the latest session.
- Titles are guessed: a short line without end punctuation is shown as a title even if it is not one. Not built: two title levels.
- 600 words is a ceiling for the whole lecture; minor topics can still be left out.
- The model can add small inferences; the lecturer checks the text.
- Needs a Zoom cloud transcript; local recordings have none; Hebrew transcription in Zoom is not verified for our account.
- The API key expires about 28/12; there is no warning.
- A "Failed" message stays until the next upload, also in a new session.
- Not built: recording input; session chooser; chapters, keywords, "related to", date, length; copy button; other formats (PDF, Word, Markdown); download of older summaries or sessions; retry button; delete summary; note for txt without timestamps; fallback model; SUMMARY_MAX_WORDS from an environment variable; escaping a closing transcript tag inside the text.
- Not verified: whether uploads over 1 MB are spooled to a temporary file.

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
- The gap line on the review page shows the numbers at the time of the count; it does not update if marks change afterwards (not built: upload the photo again).
