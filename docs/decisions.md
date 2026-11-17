# Decisions

Closed decisions only. Open items are in `project_plan.md`. Last updated: 17/11/2026.

| # | Decision | Reason (rejected alternative) | Source |
|---|---|---|---|
| D1 | Attendance counts only students physically in class. Remote (Zoom) students are not counted, and the system does not distinguish them. | The assignment defines F1 as marking attendance "in class". Rejected: a remote-attendance path (Zoom report, separate pool). | Assignment (F1, guidelines) |
| D2 | A class photo is used only to count people. No face recognition. A count gap raises an alert and never blocks. | Face recognition makes embarrassing, discriminatory errors and carries a regulatory burden. Rejected: face recognition, selfie with EXIF. | Lecturer (lecture) |
| D3 | No integration with Moodle, Zoom or university systems. Files are uploaded manually. | The assignment says no need to integrate; less work. | Assignment (guidelines) |
| D4 | Students use a mobile web app in the browser, with no installation. | KISS requirement. | Assignment (requirements) |
| D5 | Real personal data (roster, class photos) never enters the repo. Tests use synthetic data. Real data stays in git-ignored `private_data/`. | Public repo, privacy. | Own decision |
| D6 | Implementation order is F1, F2, F3, F4, F5. F1 is built in depth; F4 and F5 are thin slices. | F1 is the main feature of the assignment. Whether all five are required is a question to the lecturer (see plan). | Assignment, own decision |
| D7 | Two QR codes: a fixed QR/link for the class page (comments, polls) and a rotating QR (5-10 s) for attendance only. | A rotating code stops a photo of it being forwarded to someone outside the room. For comments and polls it would only add friction. Rejected: one rotating QR for everything. | Own decision, 17/11 |
| D8 | Identity by Google sign-in with the email on the lecturer's roster. A student whose email is not on the roster cannot register; the lecturer adds them. A device is registered once, then scan and one tap. No ID numbers are stored. | A student cannot mark for a friend just by knowing a number, and no ID storage is needed. Rejected: typed ID or name. Subject to spike S1 (in-app browsers, user cap). | Own decision, lecturer's idea |
| D9 | Presence is checked by location (within about 50 m of the building) and by network (campus IP). Only a yes/no result is stored. | The two cover each other's gaps. They are a deterrent, not proof. Indoor GPS is weak, so the range is tens of meters. Block or flag: see plan. | Own decision, 17/11 |
| D10 | F2 comments are anonymous and real time (the lecturer page refreshes automatically). Late comments go to the same place. The lecturer can hide a comment. | Shy students take part more. One mechanism serves both live and after class. | Own decision, 17/11 |
| D11 | F3 polls are anonymous, Kahoot-style, one vote per browser, no cheat protection (stated as a limitation). | The simplest possible poll. | Lecturer (lecture), own decision |
| D12 | F4: the lecturer uploads the Zoom transcript (video only as a fallback). An LLM writes the summary in a background job. The demo uses a short clip. | A transcript makes speech-to-text unnecessary, and a long job should not block the page. | Lecturer (lecture), own decision |
| D13 | F5: a critical report with no grade and no rubric. Layer 1 is cheap checks; layer 2 compares with the class, showing only aggregates. Other students' code is not run. | The lecturer rejected a rubric. Running others' code needs a sandbox. | Lecturer (lecture) |
| D14 | Lecturer pages are protected by one password stored in `.env`, never committed. | KISS and minimal friction for the lecturer. | Own decision |
| D15 | Bluetooth proximity is rejected. | A phone browser cannot do it (not supported on iPhone). | Lecture analysis |