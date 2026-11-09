# Tasks

## Done in this branch

- Monorepo skeleton, proprietary licence, and safety rules.
- Dashboard shell: Overview, Market, Quant, Strategy, Events, Risk, Portfolio, Research, Audit, Paper swaps.
- FastAPI routes, synthetic SAMPLE bars, Coinbase BTC-USD, ETH-USD, and SOL-USD display, and the sizing calculator.
- Alembic through `0009_agent_registry` on the local database at `127.0.0.1:5433`. Schema `private` holds the agent registry. `GET /api/v1/agents` reads it and cannot enable a desk. `GET /api/v1/agency/desks/{code}` reads one desk and its deny list. `GET /api/v1/audit/log` reads size-audit rows. Neither route can submit an order.
- Compose file bound to loopback, and a GitHub Actions workflow. This clone has no commits, so that workflow has not run.
- MAC-01 CLI (paper by default, $100 cap, live gate unused) and simulated testnet swaps.
- Unit tests for sizing, sample bars, Coinbase parsing, posture, MAC-01, swaps, and the web shell. They were not re-run in the 8 November 2026 docs pass.

## Sprint 1, still paper-only

- Replace the static “not configured” auth copy with a real local auth design, reviewed before any cookie is set.
- Decide the CSRF control that will exist once a cookie exists. Do not pretend it exists now.
- Sizing successes are written to `audit_events` with the correlation id. Still do not create orders. Rejected sizes write no audit row.
- The MAC-01 ledger and the simulated swap rows already exist. Daily and weekly stops on the sizing policy are still not enforced. Keep saying that.
- Pin GitHub Action SHAs after the first green CI run.
- Run the reviews listed in `docs/reviews/PENDING.md`.

## Explicitly not next

- AWS deploy. The owner has kept the app local. See ADR 0002.
- A live trading flag that boots the API.
- Using the compromised Alpaca key, or sending a paper order before the owner authorises it.
- Forking God's Eye before the data-licence audit.
- Vendoring the 21st.dev shell.
- Signing or broadcasting a swap.
