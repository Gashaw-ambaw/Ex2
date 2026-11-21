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
- Railway Trial limits and cost. The old Google secret is not yet disabled.

## Open (my decision)

- Railway Hobby or Render paid, and the budget. Python + FastAPI + SQLite stays a candidate stack until I approve it.
