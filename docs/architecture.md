# Architecture

The current inventory is `docs/architecture/current-state.md`. The delivery target, including decisions that override the November 2026 master plan, is `docs/architecture/target-state.md`. Status of each plan item is `docs/implementation-checklist.md`.

What still holds:

- The browser talks to FastAPI on `127.0.0.1:8000`. CORS allows the local Vite origins and does not send cookies.
- The API boots only when `VEYTRIX_ENV=local`, live broker mode is off, and the database host is `127.0.0.1`, `localhost`, or `postgres`.
- `POST /api/v1/risk/size` returns a share count with `execution_permitted` and `order_submitted` false.
- SAMPLE bars are synthetic. BTC-USD, ETH-USD, and SOL-USD are a Coinbase display. Neither path submits an order.
- Alpaca orders, if any, come from the MAC-01 CLI. Simulated swaps come from the paper-swap CLI. The API reads both and submits neither.
- Authentication is not implemented. The database in use on this machine is `veytrix-local-postgres` on `127.0.0.1:5433`, not the Compose publish on port 5432 (that host port is taken by another container).

```text
browser (127.0.0.1:5173)
    │  CORS, no cookies
    ▼
FastAPI (127.0.0.1:8000)
    ├── /health, /ready, /diagnostics
    ├── /market          SAMPLE in memory; Coinbase BTC-USD, ETH-USD, SOL-USD
    ├── /risk/size       decimal calculator, no order write
    ├── /strategies/mac-01   ledger read; pause / resume / kill-switch engage
    └── /paper-swaps     simulated fills, read-only
            │
            ▼
      Postgres 16 (127.0.0.1:5433 on this machine)
```

The MAC-01 runner and the swap CLI are separate processes. They are not in that HTTP path.
