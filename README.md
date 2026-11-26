# Ex2 – Web-based Teaching Tool

Status: F1 build in progress (step 6 done). Deadline: Monday 30/11/2026, 23:59.

## What it is

A web app for a class, used from the students' phones with no installation. At the end of the lecture the lecturer shows a QR code on the projector. Each student scans it, confirms their name and taps once. The lecturer gets an attendance spreadsheet, and an alert if the marks exceed the number of people counted in a class photo by more than a set tolerance. The same app lets students send anonymous comments, lets the lecturer run quick polls, summarizes a lecture from its Zoom transcript, and gives a student a critical report on their homework repository before submission.

## Problem

Taking attendance by hand costs lecture time, and a simple self-service tool is easy to cheat: marking from home, marking for a friend, or registering without being enrolled. The tool must be simple for students and the lecturer, but reliable enough to trust. Two questions must be answered:
- **Identity:** is this person enrolled in the course?
- **Presence:** is this person in the class right now?

## Users

- **Lecturer:** opens and closes attendance, takes a class photo, gets a spreadsheet and alerts, reads comments, runs polls, uploads transcripts.
- **Student in class:** scans a QR code with an Android phone.

## Scope

**In scope**
- In-class attendance (F1) with identity and presence checks and a photo-based head count.
- A spreadsheet for the lecturer (downloadable; Google Sheets as an add-on).
- The other features at the levels below.

**Out of scope**
- Students joining by Zoom are not counted, and the system does not distinguish them.
- Face recognition. The photo only counts people.
- Integration with Moodle or Zoom. Files such as transcripts are uploaded manually.
- A native mobile app.
- Personal data beyond what the course roster requires.

## Features

| # | Feature | Level |
|---|---|---|
| F1 | Attendance: QR scan, identity and presence checks, photo head count | Full (main feature) |
| F2 | Anonymous comments, live or after class | Full (simple) |
| F3 | Anonymous quick polls | Full (simple) |
| F4 | Lecture summary from a Zoom transcript | Thin slice |
| F5 | Critical report on homework repos, with a class comparison | Thin slice |

All five features are implemented, in order F1 to F5. F1 is built in depth; F4 and F5 are thin slices.

## Documents

Written in English, in Markdown.

| Document | Status |
|---|---|
| [Decisions](docs/decisions.md) | In progress |
| [Project plan](docs/project_plan.md) | Draft |
| [Tools report](docs/tools_report.md) | TBD |
| [SOW](docs/sow.md) | Draft |
| [SRS](docs/srs.md) | Draft |
| [Use cases](docs/use_cases.md) | Draft |
| [SDD](docs/sdd.md) | Draft |
| [EDD](docs/edd.md) | Draft |
| [Test plan](docs/stp.md) | Draft (F1) |
| [Results](docs/results.md) | In progress |
| [AI usage](AI_USAGE.md) | In progress |

## Quick start, usage, tests

TBD (after implementation).