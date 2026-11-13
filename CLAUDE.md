# Veytrix

Private market-research workspace for one person. Paper mode by default. The MAC-01 command-line bot can trade up to $100 live behind a gate (see below). Not investment advice.

## Safety

The API must refuse to boot if `VEYTRIX_ENABLE_LIVE_BROKER` is set, if `VEYTRIX_ENV` is not `local`, or if the database host is not `127.0.0.1`, `localhost`, or the Compose service name `postgres`. There is no auth gateway in this build, so a non-local environment cannot be made safe by a boolean.

`POST /api/v1/risk/size` calculates a long-only share count. It must keep `execution_permitted` and `order_submitted` false. Do not add an order route in this sprint.

LLM output and external content must not be able to call that calculator in a way that submits an order. Nothing in the API submits one. The MAC-01 runner is the only order path, and its input is the crossover rule alone.

Separate from the API, `python -m veytrix_ai.swapbot` is a simulated paper-swap CLI. It prices testnet pairs from read-only market data and records the fill in Postgres. It cannot sign or broadcast, and it accepts no private key. Allowed networks are Solana devnet, Ethereum Sepolia (`11155111`), and Base Sepolia (`84532`). It is not an agent tool: no LLM, prompt, or API route can trigger it, and only typed CLI commands record a swap. The helper contracts in `contracts/` are unaudited reference code and are not deployed by this build. The API can read the simulated portfolio and orders. It has no swap submit route and does not import `veytrix_ai`.

## MAC-01 exception

`services/quant/veytrix_quant/mac01` is a command-line bot that can submit real orders to the user's Alpaca Trading API account. It is paper by default. The rest of this file still holds for the API process.

- The only decider is the AAPL SMA 20/50 crossover. No LLM output, external content, or API route can reach `Mac01Engine.run`. Orders come only from `python -m veytrix_quant.mac01 run --submit` or `schedule --submit`.
- Live needs all of: config `mode: live`, `live_enabled: true`, `submit_orders: true`, env `MAC01_LIVE_CONFIRM=I_UNDERSTAND_REAL_MONEY`, `--submit`, an `expected_account_number` that matches the account, an unblocked `ACTIVE` account, and the kill switch off. Each condition has a test.
- Caps: $100 notional per buy, $100 position, 2 orders a day, one open order, long only. A sell closes the whole held quantity.
- alpaca-py may be imported only by `alpaca_trading.py` and `alpaca_data.py`. The API must not import the engine, ledger, or adapters.
- No live order has been placed by this build. The live gate has not had an independent review (see `docs/reviews/PENDING.md` item 11).

## Layout

- `apps/web` is the local dashboard. It plots only bars returned by the API.
- `services/api` is the FastAPI process.
- `services/market-data` generates the synthetic SAMPLE series in memory.
- `services/risk` is the decimal sizing module.
- `services/quant` holds MAC-01 (see above). `services/execution` holds disabled paper recorders for TradingView alert text, TradersPost webhook JSON, and SignalStack webhook JSON. They can validate a payload and write an in-memory audit row. They do not call a broker, and the API does not import them. `services/event-intelligence` is a README-only placeholder. `services/portfolio` is a README; paper-position routes live in the API and are not broker fills.
- `apps/obsidian-assistant` and `apps/grok-assistant` are separate from this trading system. They do not import the quant package, the broker adapters, or the API.
- `services/api/veytrix_api/comms` and `routers/comms.py` are agent chat: direct, group, discussion, and boardroom conversations between the user and the ten desks. Read-only against local records. They must not import MAC-01, alpaca, or `veytrix_ai`, and no route there may place an order. `live_execution` is a constant false. Replies carry an origin (`tool_verified`, `scripted`, `simulated`); no model is configured. See `docs/agent-communication/README.md`.
- `services/ai-research/veytrix_ai` is the simulated paper-swap CLI. Config is `services/ai-research/swapbot.yaml`. The kill switch lives in gitignored `var/`. Fills and balances are rows in the local database.
- `contracts/` is a Foundry project with two unaudited swap helpers, `MultiHopSwap` (original SwapRouter) and `MultiHopSwap02` (SwapRouter02). Neither is deployed. The paper-swap CLI does not sign or deploy them; they are reference only. Fee-on-transfer tokens are unsupported.
- `apps/gods-eye` explains a later fork. It does not contain upstream code.

## Checks

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
bash scripts/check.sh
```

Python 3.12 or newer. The Docker image uses `python:3.12-slim`. Node 22 is used for the web app.

Alembic: `alembic -c services/api/alembic.ini upgrade head` only when `VEYTRIX_ENV=local`.

## Honesty

Authentication is not implemented. CSRF tokens are not implemented. The rate limit is process-local. The sample chart is not a market price. Claude Code has not reviewed this tree, and Codex has not written the tests. Pending review tasks are in `docs/reviews/PENDING.md`.
