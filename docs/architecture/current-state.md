# Current state

Audit date: 8 November 2026. Branch `feature/sprint-0-foundation`. The git repository has no commits and no remote, so the whole tree is untracked. This file describes the code and the processes that were already running. It is not a claim that GitHub CI has passed.

Confidence: high for the files read and the HTTP checks below. High for the Alembic version, which was read from `127.0.0.1:5433`. Low for "CI is green", because this pass did not run `scripts/check.sh` and GitHub has never seen a commit. The paper-swap write path was not executed.

## What is running

| Process | Bind | Note |
| --- | --- | --- |
| Vite (`apps/web`) | `127.0.0.1:5173` | Already up. Not restarted. |
| Uvicorn (`veytrix_api`) | `127.0.0.1:8000` | Already up. Python 3.14.6, API 0.1.0. Not restarted. |
| `veytrix-local-postgres` | `127.0.0.1:5433` → container 5432 | Alembic head `0009_agent_registry`. |
| `daypilot-db` | `0.0.0.0:5432` | Not a Veytrix database. Do not point this app at it. |
| Supabase stacks `nexgrail` and `gridlock` | other host ports | Other projects. There is no Veytrix Supabase project. |

`docker-compose.yml` still publishes Postgres on `127.0.0.1:5432`. That host port is taken by `daypilot-db`. The database this app is using is the one on 5433, which `services/quant/README.md` already documents. Compose was not changed and was not started.

No `.env` file exists. A previous Alpaca key pair was pasted into a chat and is compromised. It must be regenerated in the Alpaca dashboard and must not be typed into this repository.

## Web app

`apps/web` is a private Vite + React 19 dashboard. Palette is obsidian (`#0b100e`) and jade (`#3dbe8b`), IBM Plex, Tailwind 4. Charts are TradingView Lightweight Charts 5.2.1 (Apache-2.0). The 21st.dev shell is not vendored; the web UI rule says it was inspected and rejected.

Routes in the shell: Overview, Agency, Market, Quant, Strategy, Events, Risk, Portfolio, Research, Audit, Paper swaps. Agency lists disabled desks and cannot enable one. Research and Audit are real pages, not disabled links. The Agency page on the already-running Vite server shows the registry as unavailable until the API process is restarted.

Market prices come from the API. SAMPLE remains a synthetic series. BTC-USD, ETH-USD, and SOL-USD are Coinbase Exchange public data for display on this machine. The Market page was drawing a BTC-USD 1-minute chart during this audit. If the API is down, the page is supposed to show an error and invent nothing. That failure path was not re-tested here.

The Strategy page is read-only apart from pause, resume, and engage-kill-switch. There is no buy or sell button. The overview card "No broker is connected" matches this machine: the adapter exists, and no key is configured.

## API

FastAPI under `/api/v1`. Swagger UI is off. OpenAPI JSON is served and a copy lives in `packages/shared/openapi.json`.

Boot (`services/api/veytrix_api/settings.py`) raises `BootRefused` when `VEYTRIX_ENABLE_LIVE_BROKER` is set, when `VEYTRIX_ENV` is not `local`, or when the database host is not `127.0.0.1`, `localhost`, or `postgres`. Alembic uses the same check. There is no auth flag that can override this. This session did not restart the process to re-prove the refusal; `tests/test_posture.py` covers it, and those tests were not re-run in this pass.

Migration `0009_agent_registry` added schema `private` (`agents`, `agent_permissions`, `agent_runs`) and made `audit_events` append-only. The nine desks are seeded disabled and cannot submit, sign, or transfer. The tree has `GET /api/v1/agents`, `GET /api/v1/system/status`, `GET /api/v1/audit/log`, and `GET /api/v1/agency/desks/{code}`. On 8 November 2026 the listener PID 11188 still served `GET /api/v1/agents` (200) and returned 404 for the audit log and the desk path. That process was not restarted.

Live `GET /api/v1/diagnostics` returned `auth: not_configured`, `csrf` not implemented, `execution_permitted: false`, `live_broker: disabled`, rate limit process-local. CORS allows the local Vite origins and does not send cookies.

Working routes (from the routers; health, diagnostics, the instrument list, and the three tickers were called live):

| Method | Path | Role |
| --- | --- | --- |
| GET | `/api/v1/health` | Liveness. No database. |
| GET | `/api/v1/ready` | `SELECT 1`. |
| GET | `/api/v1/diagnostics` | Posture. No secrets. |
| GET | `/api/v1/system/status` | Local posture and a desk count. No broker balance. Not on the process that was already listening. |
| GET | `/api/v1/agents` | Nine disabled desks. GET only. PID 11188 returned 200 on 8 November 2026. |
| GET | `/api/v1/audit/log` | Size-audit rows. GET only. PID 11188 returned 404. |
| GET | `/api/v1/agency/desks/{code}` | One desk and its deny list. No enable method. PID 11188 returned 404. |
| GET | `/api/v1/market/instruments` | SAMPLE plus Coinbase BTC-USD, ETH-USD, SOL-USD. |
| GET | `/api/v1/market/instruments/{symbol}/bars` | SAMPLE bars, or Coinbase candles for the three products. |
| GET | `/api/v1/market/instruments/{symbol}/ticker` | Coinbase last trade for those three products. |
| POST | `/api/v1/risk/size` | Long-only share count. `execution_permitted` and `order_submitted` stay false. |
| GET/POST/DELETE | `/api/v1/portfolio/positions` | Local paper sizes. Not broker fills. |
| GET/POST/DELETE | `/api/v1/research/notes` and `/source-events` | Local notes. No model provider. |
| GET | `/api/v1/audit/size-journal` | Recorded sizing requests. |
| GET | `/api/v1/strategies/mac-01/status`, `/signals`, `/orders`, `/performance`, `/chart` | Ledger read. |
| POST | `/api/v1/strategies/mac-01/pause`, `/resume`, `/kill-switch` | Flags only. Kill switch can be engaged, not released. |
| GET | `/api/v1/paper-swaps/portfolio`, `/orders` | Simulated fills. No submit route. |

Nothing in the API imports `veytrix_ai` or the MAC-01 engine. alpaca-py may be imported only by `alpaca_trading.py` and `alpaca_data.py`.

## MAC-01

`services/quant/veytrix_quant/mac01`. The only decider is the AAPL daily SMA 20/50 crossover. Orders come only from `python -m veytrix_quant.mac01 run --submit` or `schedule --submit`.

`config/mac-01.yaml` is paper, `submit_orders: false`, `live_enabled: false`, `max_notional_per_trade` and `max_position_notional` of `100.00`, `max_orders_per_day: 2`, long only. The scheduler is 09:35 America/New_York. The Strategy page showed last run "never".

Live submission needs all eight conditions in `services/quant/README.md`: `mode: live`, `live_enabled: true`, `submit_orders: true`, `MAC01_LIVE_CONFIRM=I_UNDERSTAND_REAL_MONEY`, `--submit`, matching `expected_account_number`, an unblocked `ACTIVE` account, and the kill switch off. No live order has been placed. No paper order has been placed from this tree either. This pass did not call Alpaca.

## Simulated swaps

`services/ai-research/veytrix_ai` prices Solana devnet, Ethereum Sepolia (`11155111`), and Base Sepolia (`84532`) from read-only calls and records a simulated fill. It accepts no private key and does not sign or broadcast. `contracts/` is an unaudited Foundry project (`MultiHopSwap`, `MultiHopSwap02`). Foundry has not been run here. The contracts are not deployed.

`record_swap` adds the order row and then the fill row in one transaction. The foreign key `fk_paper_swap_fills_order_id` is on the local database. A fill-before-order failure was in progress with another worker. This pass did not edit `services/ai-research/veytrix_ai/**` or `tests/test_swapbot*.py`, and did not run a swap, so that ledger path is not signed off.

## Placeholders

`services/execution` and `services/event-intelligence` are README-only. `services/portfolio` is a README; the position routes live in the API. `apps/gods-eye` explains a later fork and contains no upstream code. There is no iOS app, no SQS outbox, no AWS account in this repo, and no DayPilot client. The `daypilot-db` container is not wired to Veytrix.

## Dependencies and checks

Python project (`pyproject.toml`): FastAPI, SQLAlchemy, Alembic, psycopg, Pydantic, PyYAML, Uvicorn, and alpaca-py `>=0.45,<0.46` for MAC-01 only. Dev: pytest, ruff, httpx, pip-audit. Python requirement is 3.12 or newer.

Web: React 19, React Router 7, Vite 8, Vitest, TypeScript, Tailwind 4, Lightweight Charts 5.2.1. Node 22 in CI.

Checks that exist: `scripts/check.sh` (ruff, pytest, web typecheck, Vitest, web build, `scripts/scan_secrets.py`), `.github/workflows/ci.yml` (those plus `npm audit --audit-level=high` and `pip-audit`), `.gitleaks.toml`, `.pre-commit-config.yaml` (ruff only). Action versions are floating tags (`@v4`, `@v5`), not commit SHAs. Pre-commit does not run the secret scan.

## Auth, jobs, AWS

Authentication is not implemented. There is no session, MFA, or CSRF token. There is no job runner in the API. MAC-01 `schedule` is a CLI loop, and it was not running. AWS is not in this tree. Secrets Manager, ECS, and SQS are absent.

## Docs that were wrong

Before this pass, `services/execution/README.md` said the repository had no broker adapter. `services/api/README.md` listed only SAMPLE. `services/market-data/README.md` said the package never calls an exchange. `docs/architecture.md` said this sprint had no execution component and showed Postgres on 5432 only. `docs/SECURITY.md` said the build cannot place a live order because there is no order route. Those statements are corrected in place. The API still has no order route. The MAC-01 CLI can submit if its gate is met.
