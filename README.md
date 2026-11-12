# Ex2 – Web-based Teaching Tool

> **Status:** Stage 1 (definition). Design phase, no code yet.
> **Deadline:** 25/11/2026 (check Moodle for updates).

A set of web-based teaching tools for the classroom, used from the students'
smartphones. The main feature is automatic attendance with minimal involvement
of the lecturer, designed to resist cheating.

## Problem

Taking attendance by hand costs the lecturer lecture time. A naive self-service
system is easy to cheat: students can mark attendance from home, mark it for a
friend, or register without being enrolled. We need a tool that is simple
(KISS) for students and lecturers, but still reasonably trustworthy.

Two separate questions must be answered:
- **Identity:** is this person enrolled in the course?
- **Presence:** is this person really in the class right now?

## Users

- **Lecturer:** opens and closes the attendance, photographs the class, and
  receives a spreadsheet and alerts.
- **In-class student:** scans a QR code and marks attendance from a
  smartphone, with no installation.
- **Remote student** (e.g. joining via Zoom): attends remotely and is recorded
  separately.

## Success metrics (initial, to be refined)

| Metric | Target |
|--------|--------|
| Speed | At least 95% of present students are marked within the 2-minute window |
| Plausibility check | The lecturer is alerted when in-class marks exceed the photo count by more than a tolerance (initial value: 5) |
| Lecturer effort | 3–4 actions per class (open, photo, close, export) |

## Scope

**In scope**
- In-class attendance (main feature) with checks for identity and presence,
  including a lecturer photo-based headcount.
- Remote attendance (e.g. Zoom), as a separate and clearly marked mode.
  *(Required by the lecturer in class; planned after in-class attendance.)*
- A spreadsheet for the lecturer (online and downloadable).
- The other assignment features, at the levels listed below.

**Out of scope**
- Face recognition. The photo count only counts people; it identifies no one.
- Real integration with Moodle or Zoom (no API integration; files such as
  reports and recordings are uploaded manually).
- A native mobile app (web app only).
- Storing personal data beyond what the course roster requires.

## Features and priority (proposal, to be confirmed)

| # | Feature | MoSCoW | Planned level |
|---|---------|--------|---------------|
| F1 | Attendance: self-marking in class + lecturer photo-based headcount | Must | Full |
| F1b | Remote attendance (Zoom) | Should | Design first, implementation later |
| F2 | Real-time / offline comments and suggestions | Should | Full (simple) |
| F3 | On-the-spot polls | Should | Full (simple) |
| F4 | ML summary of the class video | Could | Thin slice |
| F5 | LLM homework review and comparison | Could | Thin slice |

## Working assumptions (not final decisions)

- Attendance is marked once, at the end of the class, within a 2-minute window.
- The QR code on the projector rotates every 5–10 seconds (to be measured).
  Scanning opens the attendance page only while that QR is valid; the student
  then has about 20 seconds to submit, otherwise scans again. The page is tied
  to the student's browser (session cookie), so the link cannot be forwarded.
- Each roster ID can be marked once per class. A device that marks several IDs
  triggers an alert.
- The lecturer photographs the class during the window. People are counted (no
  faces, no identification), and an alert is shown when in-class marks exceed
  the count by more than a tolerance.
- Late students are added manually by the lecturer and labelled "manual".
- Temporary data (class photo, sessions) is deleted after the class. The real
  roster and class photos are never committed to this repository.
- **Known limit:** an in-class student can still mark for an absent friend. The
  photo count is an aggregate indicator, not proof.

## Initial risks

- Cheating beyond the aggregate check (relay, marking for a friend).
- Slow or crowded network in class during the demo.
- Accuracy of the people-counting model.
- Privacy of roster data and class photos.
- Not enough time (solo, five features) and a live demo in front of the class.

## Open questions

- How is remote attendance recorded? For example, the lecturer uploads the Zoom
  participants report and the system applies a presence threshold, versus a
  separate check-in.
- Which identifier may be stored (national ID or student number), and for how
  long?
- Does "online spreadsheet" mean Google Sheets specifically?
- Is a full implementation of all five features required?
- Which people-counting method, and which tolerance, on real class photos?

## Documents

Documents are written in English, in Markdown.

| Document | Status |
|----------|--------|
| [Decisions](docs/decisions.md) | TBD |
| [Project plan](docs/project_plan.md) | TBD |
| [Tools report](docs/tools_report.md) | TBD |
| [SOW](docs/sow.md) | TBD |
| [SRS](docs/srs.md) | TBD |
| [Use cases](docs/use_cases.md) | TBD |
| [SDD](docs/sdd.md) | TBD |
| [EDD](docs/edd.md) | TBD |
| [Test plan](docs/stp.md) | TBD |
| [Results](docs/results.md) | TBD |
| [AI usage](AI_USAGE.md) | TBD |

## Quick start, usage, tests

TBD (after implementation).