# API

FastAPI service. It binds to loopback and does not submit an order.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/health` | Liveness. Does not touch the database. |
| GET | `/api/v1/ready` | Readiness. `SELECT 1`. Returns 503 when the database is down. |
| GET | `/api/v1/diagnostics` | Posture. No secrets. Auth is `not_configured`. |
| GET | `/api/v1/market/instruments` | Synthetic SAMPLE, plus Coinbase BTC-USD, ETH-USD, and SOL-USD. |
| GET | `/api/v1/market/instruments/{symbol}/bars` | SAMPLE bars, or Coinbase candles for those three products. |
| GET | `/api/v1/market/instruments/{symbol}/ticker` | Coinbase last trade for BTC-USD, ETH-USD, or SOL-USD. |
| POST | `/api/v1/risk/size` | Long-only paper share count. Does not create an order. |
| GET, POST, DELETE | `/api/v1/portfolio/positions` | Local paper sizes. Not broker fills. |
| GET, POST, DELETE | `/api/v1/research/notes`, `/source-events` | Local notes. No model provider. |
| GET | `/api/v1/audit/size-journal` | Recorded sizing requests. |
| GET | `/api/v1/audit/log` | Append-only size audit rows. GET only. An unsafe payload returns 503. |
| GET | `/api/v1/agency/desks/{code}` | One disabled desk and its deny list. Cannot enable it. |
| GET | `/api/v1/strategies/mac-01/*` | MAC-01 ledger read: status, signals, orders, performance, chart. |
| POST | `/api/v1/strategies/mac-01/pause`, `/resume`, `/kill-switch` | Control flags. The kill switch can only be engaged here. |
| GET | `/api/v1/paper-swaps/portfolio`, `/orders` | Simulated testnet fills. No submit route. |

The process refuses to boot when `VEYTRIX_ENABLE_LIVE_BROKER` is set, when `VEYTRIX_ENV` is not `local`, or when the database host is not `127.0.0.1`, `localhost`, or the Compose name `postgres`.

Alembic upgrades run only for that same local posture. Swagger UI is off so the browser does not load a documentation CDN. The OpenAPI document is `/api/v1/openapi.json`.

Authentication and CSRF tokens are not implemented. CORS allows only the local Vite origins and does not allow credentials. The rate limit is process-local.

Orders to Alpaca, if any, come from the MAC-01 CLI in `services/quant`, not from this process. See the root `README.md` for the full route table.

Run it from a virtualenv after `pip install -e ".[dev]"`, on `127.0.0.1` only:

```bash
alembic -c services/api/alembic.ini upgrade head
uvicorn veytrix_api.main:app --host 127.0.0.1 --port 8000
```
