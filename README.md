# Ex2 – Class Attendance Tool

> **Status:** early draft. Design phase, no code yet.

A web-based classroom attendance system. Students mark their own attendance
from a smartphone, with minimal involvement of the lecturer, and the system
is designed to resist cheating.

## Problem

Taking attendance by hand wastes lecture time. A naive self-service system is
easy to cheat: students can mark attendance from home, mark it for a friend,
or people who are not enrolled can register. We need a tool that is simple
(KISS) for students and lecturers, but still reasonably trustworthy.

Two separate questions must be answered:
- **Identity:** is this person enrolled in the course?
- **Presence:** is this person really in the class right now?

## Scope

**In scope**
- In-class attendance (main feature) with checks for identity and presence.
- Remote attendance (e.g. students joining via Zoom), as a required, separate
  and clearly marked mode. *(Requirement stated by the lecturer in class.)*
- A spreadsheet for the lecturer (online and downloadable).
- The other assignment features, at the levels listed below.

**Out of scope**
- Face recognition.
- Real integration with Moodle or Zoom (no API integration; recordings and
  files are uploaded manually).
- A native mobile app (web app only).
- Storing personal data beyond what the course roster requires.

## Features and planned level (proposal, to be confirmed)

| # | Feature | Planned level |
|---|---------|---------------|
| F1 | Automatic attendance (in-class and remote) | Full |
| F2 | Real-time / offline comments and suggestions | Full (simple) |
| F3 | On-the-spot polls | Full (simple) |
| F4 | ML summary of the class video | Thin slice |
| F5 | LLM homework review and comparison | Thin slice |

## Open questions

- May the system store names and IDs from the class roster?
- Does "online spreadsheet" mean Google Sheets specifically?

## Documents

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

## Quick start, usage, tests

TBD (after implementation).