# Tasks

Status words: TODO, IN PROGRESS, BLOCKED, VERIFIED. VERIFIED here means a local check passed. It does not mean Codex reviewed it, and it does not mean the phase gate is closed.

## VERIFIED locally, awaiting Codex

- Registry through `0010_futures_desk` on `127.0.0.1:5433`. Ten desks, all disabled, none can trade.
- `GET /api/v1/futures/posture` refuses Topstep automation and does not call a broker.
- Read-only routes from earlier passes: agents, desk detail, audit log, shield and reservation previews, supervisor tool check, reminders, scheduler status, live-gate evidence, local reconciliation, risk log, market health, treasury projection, paper-swap posture.
- Yellow warning notes removed from the web UI. Red failure alerts remain.

## TODO

- Replace the running API once at the end of a pass that adds a route, then confirm `GET /api/v1/agents` returns 200.
- Record the `scripts/check.sh` totals in `docs/implementation-checklist.md` after that command exits 0.

## BLOCKED

- Alpaca paper read and the first paper order. Needs regenerated keys, then a separate written yes. Do not paste keys into chat.
- Live trading. Separate authorisation. The gate stays unused.
- Supabase project, Auth, and MFA. Needs organisation, region, and an approved cost.
- AWS workers, SQS, and Secrets Manager. You chose local-only.
- DayPilot Wednesday meeting. Time is still TBD. Do not use `daypilot-db`.
- Model provider and chat. No model id is configured.
- Apple distribution and the iOS app.
- Bank payout approval and the legal, tax, and benefits review.
- Pushing this branch. A normal push was labelled a force-push and refused. Do not use `--force`.
- Codex review. The command is not installed.

## Explicitly not next

- An order route, a paper submit, a live submit, a signed swap, a mainnet RPC, or a bank transfer.
