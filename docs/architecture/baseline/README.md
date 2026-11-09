# Baseline, 8 November 2026

Captured from the processes that were already listening. Nothing was restarted.

| Surface | Where | What was seen |
| --- | --- | --- |
| Overview | `http://127.0.0.1:5173/` | Obsidian and jade shell. Orders "Not sent". Live broker "Disabled". Authentication "Not configured". BTC-USD, ETH-USD, and SOL-USD prints loaded from Coinbase. |
| Market | `http://127.0.0.1:5173/market` | BTC-USD selected. Live print and a 1-minute Coinbase candle chart rendered. |
| Strategy | `http://127.0.0.1:5173/strategy` | MAC-01 paper, cap $100.00, 2 orders a day, submit off, live off, last run never. Pause, resume, and engage-kill-switch only. |

Screenshots: `baseline-overview.png`, `baseline-market.png`, `baseline-strategy.png`.

The prices in those images are a personal display at about 23:58 UTC. They are not a record to trade on, and they will be wrong within minutes.

API checks at the same time, all HTTP 200:

- `GET /api/v1/health` returned `status: ok`
- `GET /api/v1/diagnostics` returned `env: local`, `live_broker: disabled`, `auth: not_configured`, `execution_permitted: false`
- `GET /api/v1/market/instruments/BTC-USD/ticker`, `ETH-USD`, and `SOL-USD` returned `source_id: coinbase-exchange` and a `trade_time` on 2026-11-08

Postgres `veytrix-local-postgres` on `127.0.0.1:5433` reported Alembic `0008_paper_swaps`. No `.env` file was present. No Alpaca call was made.
