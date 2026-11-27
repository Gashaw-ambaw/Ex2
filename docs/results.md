# Results

Status: F1-F3 built and live-checked; F4-F5 [fill on 29/11]. Date: 27/11/2026.
MEASURED = seen in a real run; NOT VERIFIED = not checked. Every check with its date and setup: [test_log.md](test_log.md).

## Conclusion

Attendance (F1), comments (F2) and polls (F3) work end to end on real Android devices (phones and a tablet) with the deployed app. The class photo count (S4): [fill on 28/11]. F4-F5: [fill on 29/11].

## Against the SOW

| Deliverable (`sow.md` section 2) | Status | Evidence |
|---|---|---|
| F1 Attendance | Met, except the photo count (S4, [fill on 28/11]). Location gives a flag, not a block; the hall was not tested (S3). | `test_log.md`: F1 live checks, F1 rehearsal (TC-43), S2 load check (TC-44) |
| F2 Comments, F3 Polls | Met | `test_log.md`: F2 live check, F3 live check |
| F4 Lecture summary (thin) | [fill on 29/11] | |
| F5 Repo report (thin) | [fill on 29/11] | |
| Documents | [fill on 30/11] | |
| Code, tests, quick start | 350 automated tests pass (MEASURED, pytest, 27/11). Quick start: [fill on 29/11]. | `tests/` |
| Live demo | 8/12/2026, not yet | |

## Key results

- MEASURED [TC-44] 100 marks sent at once to a local server: each student recorded once; the last reply after 2.8 s (limit 60 s). Railway was not tested.
- MEASURED [TC-43, NFR-02] Rehearsal, second scan: about 10 s from scan to "Marked at" (rough, by hand).
- MEASURED [TC-43, NFR-04] Lecturer actions per class, counting Review: 4 without the photo; 5 with it, above the 3-4 target. Whether Review counts is open until S4.
- MEASURED [TC-25, TC-17] A phone that had already marked another student was blocked; a tester not on the roster got "Contact the lecturer".
- MEASURED [TC-65, TC-59] While a poll was open the lecturer page showed only the number of answers; after Close the phones showed Correct or Wrong.

## Not tested

NOT VERIFIED: iPhone; the WhatsApp in-app browser; location in the real hall (S3); the deployed app under load and on campus Wi-Fi; NFR-03 (95% of students marked within the window); the 100 test-user cap and the Google publishing status; the 120-day cookie; Hebrew names in the exported CSV.

## Lessons learned

- A GET route that wrote data made duplicate rows (probably browser preload, not verified). Every action that changes data is a POST (S1).
- Railway "Redeploy" runs the old commit; use "Deploy latest commit" (S1).
- The load check ran on a local server, because the deployed app has no test route and no test accounts (S2). A number for Railway needs its own setup.
- Give each test phone its own Google account: a location flag showed on the wrong phone, probably because both phones used one account (not proven).
- A live count per option on a projected page can influence the answers, so poll results appear only after Close (D36).

## Main known limits

Full lists in `test_log.md`: "F1 known limits" and "F2-F3 known limits".

- Review and export show only the latest session; a session started by mistake hides the first one's marks.
- A student who once chose "never allow" for location gets a location flag on every later mark from that device.
- The CSV export does not escape values that start with `=`, `+`, `-` or `@`.
- Clearing cookies or a second browser gets past the comment time limit and the one-answer rule.

## Future

S3 (location in the hall); S4 if not done by 28/11; F4-F5 beyond the thin slice; the optional flows (D35); iPhone and WhatsApp tests; a load check on the deployed app. [fill on 29/11]
