# Results

Status: F1-F3 built and live-checked; the class photo count (S4) built and live-checked with limits; F4-F5 [fill on 29/11]. Date: 28/11/2026.
MEASURED = seen in a real run; NOT VERIFIED = not checked. Every check with its date and setup: [test_log.md](test_log.md).

## Conclusion

Attendance (F1), comments (F2) and polls (F3) work end to end on real Android devices (phones and a tablet) with the deployed app. The class photo count (S4) is built: on my laptop 11 of 11 test photos were within 10% of my count; on the deployed app one of these photos gave the same count as on the laptop. F4-F5: [fill on 29/11].

## Against the SOW

| Deliverable (`sow.md` section 2) | Status | Evidence |
|---|---|---|
| F1 Attendance | Met, with limits: location gives a flag, not a block; the hall was not tested (S3), also for the head count. | `test_log.md`: F1 live checks, F1 rehearsal (TC-43), S2 load check (TC-44), S4 spike, S4 live check |
| F2 Comments, F3 Polls | Met | `test_log.md`: F2 live check, F3 live check |
| F4 Lecture summary (thin) | [fill on 29/11] | |
| F5 Repo report (thin) | [fill on 29/11] | |
| Documents | [fill on 30/11] | |
| Code, tests, quick start | 377 automated tests pass (MEASURED, pytest, 27/11). Quick start: [fill on 29/11]. | `tests/` |
| Live demo | 8/12/2026, not yet | |

## Key results

- MEASURED [TC-44] 100 marks sent at once to a local server: each student recorded once; the last reply after 2.8 s (limit 60 s). Railway was not tested.
- MEASURED [TC-43, NFR-02] Rehearsal, second scan: about 10 s from scan to "Marked at" (rough, by hand).
- MEASURED [TC-43, NFR-04] Lecturer actions per class, counting Review: 4 without the photo, as rehearsed. With the photo it is 5 (counted, not rehearsed), above the 3-4 target; kept for now.
- MEASURED (S4 spike, laptop, 11 photos) Head count with tiling: all within 10%, mean absolute error 3.5% (without tiling: 7 of 11, 8.9%). The settings were chosen on 5 of these photos.
- MEASURED [TC-27] Deployed app: a real photo (24 people, 30 hand marks) gave "counted 25, gap 5".
- Approximate (read from the Railway pages, 28/11): memory about 430 MB after several counts, under the 500 MB limit of the spike and the 1 GB RAM limit of the Trial plan.
- MEASURED [TC-25, TC-17] A phone that had already marked another student was blocked; a tester not on the roster got "Contact the lecturer".
- MEASURED [TC-65, TC-59] While a poll was open the lecturer page showed only the number of answers; after Close the phones showed Correct or Wrong.

## Not tested

NOT VERIFIED: other halls and larger classes; a photo upload from a phone camera; "Counting failed" on the live site (TC-30 only); iPhone; the WhatsApp in-app browser; location in the real hall (S3); the deployed app under load and on campus Wi-Fi; NFR-03 (95% of students marked within the window); the 100 test-user cap and the Google publishing status; the 120-day cookie; Hebrew names in the exported CSV.

## Lessons learned

- A GET route that wrote data made duplicate rows (probably browser preload, not verified). Every action that changes data is a POST (S1).
- Railway "Redeploy" runs the old commit; use "Deploy latest commit" (S1).
- The load check ran on a local server, because the deployed app has no test route and no test accounts (S2). A number for Railway needs its own setup.
- Give each test phone its own Google account: a location flag showed on the wrong phone, probably because both phones used one account (not proven).
- A downloaded model script had a bug in its duplicate filter (0 of 5 photos). A sanity check before more tuning found it; counting the photo in tiles then reduced most of the remaining error (S4).
- A live count per option on a projected page can influence the answers, so poll results appear only after Close (D36).

## Main known limits

Full lists in `test_log.md`: "F1 known limits" and "F2-F3 known limits".

- Review and export show only the latest session; a session started by mistake hides the first one's marks.
- A student who once chose "never allow" for location gets a location flag on every later mark from that device.
- The CSV export does not escape values that start with `=`, `+`, `-` or `@`.
- Clearing cookies or a second browser gets past the comment time limit and the one-answer rule.
- The head count is approximate, and the gap line does not update if marks change after the count.

## Future

S3 (location in the hall); the head count in the real hall; fewer lecturer actions; F4-F5 beyond the thin slice; the optional flows (D35); iPhone and WhatsApp tests; a load check on the deployed app. [fill on 29/11]
