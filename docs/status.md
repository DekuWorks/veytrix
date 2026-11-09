# Status

Date: 9 November 2026. Branch: `feature/sprint-0-foundation`. This file is the progress note asked for by the remaining-build work order. It is not a claim that paper production is running.

## What is running here

- Vite on `127.0.0.1:5173`.
- FastAPI on `127.0.0.1:8000`, local only. The process that was already listening does not serve routes added after it started until the one restart at the end of a pass that adds routes.
- Postgres `veytrix` on `127.0.0.1:5433`. Alembic head `0010_futures_desk`. `daypilot-db` on port 5432 was not used.

## Verified this pass

- Yellow warning notes were removed from the web UI. Red failure alerts, navigation, figures, and the sentences that say no order is sent stayed.
- `FUTURES-01` is a disabled registry row. It cannot submit, sign, or transfer. `GET /api/v1/futures/posture` says Topstep automation is disabled, the account is not connected, and MES/MNQ are labels only. POST is 405. No broker call.
- Coinbase display routes were not replaced.

## Not verified

Codex is not installed. Nothing in this file is an independent review. Alpaca was not called. No paper order and no live order was sent. No Supabase, AWS, Apple, model, or bank resource was created.

## Push

`origin` is `https://origin.cursor.com/dekuworks/veytrix.git`. A normal `git push` of this branch was refused by a check that labelled it a force-push. It was not retried and `--force` was not used. The remote was not overwritten.
