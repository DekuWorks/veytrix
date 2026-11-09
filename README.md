# Veytrix

Private market-research desk for one person. Not investment advice, and not a hosted product.

Intelligence and execution stay apart. The API calculates a long-only paper share count and never submits an order. Live broker mode refuses to boot.

One exception: the MAC-01 command-line bot (`services/quant`) can trade up to $100 of AAPL on your own Alpaca account. It runs on paper by default. Live trading with real money needs every live-gate condition in `services/quant/README.md`. Only the AAPL SMA 20/50 crossover decides; no model or web page can place an order.

## Run locally

Requirements: Python 3.12 or newer (3.14 works for local checks), Node 22, and optionally Docker.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
npm --prefix apps/web ci
```

Create a local env file yourself if you want one. It is gitignored. Use these placeholders and do not reuse them anywhere else. `local-dev-only` is not a production secret:

```text
VEYTRIX_ENV=local
VEYTRIX_ENABLE_LIVE_BROKER=0
POSTGRES_PASSWORD=local-dev-only
DATABASE_URL=postgresql+psycopg://veytrix:local-dev-only@127.0.0.1:5432/veytrix
VEYTRIX_RATE_LIMIT_PER_MINUTE=360
VEYTRIX_LOG_LEVEL=INFO
VITE_API_BASE_URL=http://127.0.0.1:8000
```

API, bound to loopback:

```bash
alembic -c services/api/alembic.ini upgrade head
uvicorn veytrix_api.main:app --host 127.0.0.1 --port 8000
```

Web, also loopback:

```bash
npm --prefix apps/web run dev
```

The dev server is `http://127.0.0.1:5173`. It reads bars and sizing results from the API. If the API is down, the market page shows an error and does not invent prices. Coinbase BTC-USD, ETH-USD, and SOL-USD quotes are a personal display on this machine. No order is sent.

Docker Compose publishes Postgres, the API, and the built web app on `127.0.0.1` only:

```bash
docker compose up --build
```

Alembic runs inside the API container only when `VEYTRIX_ENV=local`.

## Checks

```bash
bash scripts/check.sh
```

That runs Ruff, pytest, the web typecheck, Vitest, the web build, and the secret scan. `make check` calls the same script.

## What the API does

| Method | Path | Behaviour |
| --- | --- | --- |
| GET | `/api/v1/health` | Liveness. No database. |
| GET | `/api/v1/ready` | `SELECT 1`. 503 if the database is down. |
| GET | `/api/v1/diagnostics` | Paper posture. No secrets. Auth is not configured. |
| GET | `/api/v1/market/instruments` | Synthetic SAMPLE, plus Coinbase BTC-USD, ETH-USD, and SOL-USD. |
| GET | `/api/v1/market/instruments/SAMPLE/bars` | Seeded weekday bars. Not a market price. |
| GET | `/api/v1/market/instruments/{symbol}/ticker` | Coinbase last trade for BTC-USD, ETH-USD, or SOL-USD. Personal display. No order is sent. |
| POST | `/api/v1/risk/size` | Calculates a share count. Does not create an order. |
| GET | `/api/v1/strategies/mac-01/status` | MAC-01 mode, caps, controls, and last run, from the local ledger. |
| GET | `/api/v1/strategies/mac-01/signals` | Recorded crossover signals and decisions. |
| GET | `/api/v1/strategies/mac-01/orders` | Orders the runner sent. Read-only. |
| GET | `/api/v1/strategies/mac-01/performance` | Realised P&L from fills, unrealised from the last position snapshot. |
| GET | `/api/v1/strategies/mac-01/chart` | Stored closes with SMA lines and crossover markers. |
| POST | `/api/v1/strategies/mac-01/pause`, `/resume`, `/kill-switch` | Control flags only. The kill switch can only be engaged here. |
| GET | `/api/v1/paper-swaps/portfolio` | Simulated testnet balances. Nothing is signed. |
| GET | `/api/v1/paper-swaps/orders` | Simulated swap fills. Read-only. |

OpenAPI JSON is `/api/v1/openapi.json`. The Swagger UI is off. The committed copy is `packages/shared/openapi.json`.

## MAC-01

Steps (regenerate keys, fill `.env`, paper dry run, paper submit, live dry run, live submit or schedule) are in `services/quant/README.md`. The `.env` placeholders are:

```text
ALPACA_PAPER_API_KEY=
ALPACA_PAPER_SECRET_KEY=
ALPACA_LIVE_API_KEY=
ALPACA_LIVE_SECRET_KEY=
# MAC01_LIVE_CONFIRM=I_UNDERSTAND_REAL_MONEY
```

The dashboard's Strategy page shows the mode, health, chart, P&L, signals, and orders. It has no buy or sell button.

## Safety

- Do not set `VEYTRIX_ENABLE_LIVE_BROKER`. The process exits.
- Do not start a non-local environment. There is no auth gateway, so the process exits.
- The API installs and imports no broker client. alpaca-py is a dependency of the MAC-01 command line only, and only its two adapter modules import it (a contract test checks this).
- The paper-swap CLI records simulated testnet fills from read-only prices. It cannot sign or broadcast, and the API cannot submit a swap. The contracts in `contracts/` are unaudited reference code.
- Daily and weekly loss stops are stored policy. They are not enforced against a ledger. Stops can fail.
- Authentication and CSRF tokens are not implemented. CORS allows only the local Vite origins and does not send cookies.

See `docs/SECURITY.md`, `docs/architecture.md`, and `docs/adr/0001-paper-only-execution-boundary.md`.

## Licence

Proprietary, DekuWorks, all rights reserved. Third-party notices are in `docs/licenses/THIRD_PARTY.md`.
