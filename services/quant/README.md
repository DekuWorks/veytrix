# Quant: MAC-01

MAC-01 trades AAPL on your own Alpaca Trading API account. The only decider is the daily SMA 20/50 crossover in `veytrix_quant/mac01/strategy.py`. No LLM, web page, note, API route, or source event can place an order. Only the `python -m veytrix_quant.mac01` command line (`run --submit` or `schedule --submit`) submits.

Not investment advice. Live mode spends real money.

## Rule

- BUY when the previous fast SMA was at or below the previous slow SMA and the current fast SMA is above the current slow SMA. SELL is the mirror. Otherwise HOLD.
- It needs at least 51 completed daily closes (adjusted for splits, dividends, and spin-offs). The runner fetches 100.
- One signal per completed session. A rerun keeps the stored signal.

## Orders

| Signal | Holding AAPL | Order |
| --- | --- | --- |
| BUY | no | Notional market DAY buy for `max_notional_per_trade` (default $100.00), limited by room under `max_position_notional` and rounded down to cents |
| BUY | yes | None (long only, one position) |
| SELL | yes | Market DAY sell of the whole held quantity |
| SELL | no | None. MAC-01 never shorts |
| HOLD | either | None |

Before any submit, the runner reconciles its ledger with Alpaca (`get_order_by_client_id`), reads the position (`get_all_positions`) and open orders (`get_orders`), and checks the asset is tradable and fractionable. It refuses if any of these hold:

- an AAPL order is already open (one at a time)
- `max_orders_per_day` (at most 2) orders already exist today in this mode
- cash or buying power is below the notional
- yesterday's equity minus today's equity has reached `daily_loss_cutoff_usd`
- part of the position is held for another order
- the time is outside the regular session after the signal session (09:30 to 15:45 New York)

Every order has a deterministic `client_order_id`: `mac01-<mode>-` followed by a SHA-256 prefix of (mode, strategy version, symbol, signal date, side). The id is written to Postgres as `pending_submit` before the broker call. A rerun finds it and does not submit again. If a submit times out, the runner looks the order up by that id and never retries the submit.

alpaca-py sets no HTTP timeout and retries 429 and 504 responses, including on `POST /v2/orders`. The adapter sets a 10-second timeout and turns retries off.

## Schedule

`schedule` runs at 09:35 New York on each trading day from the Alpaca calendar, which skips holidays and handles early closes. At that time the previous session's daily bar is final, and a notional market DAY order is inside regular hours. Alpaca fills fractional and notional market orders only in regular hours. Extended hours need limit orders, which MAC-01 does not send.

## Modes and the live gate

`mode: paper` (the default) uses `ALPACA_PAPER_*` keys and `TradingClient(paper=True)`. Submitting needs `submit_orders: true` in the config and `--submit`.

`mode: live` uses `ALPACA_LIVE_*` keys and `TradingClient(paper=False)`. Submitting needs all of the following, or the runner refuses with exit code 2 and lists every missing item:

1. config `mode: live`
2. config `live_enabled: true`
3. config `submit_orders: true`
4. env `MAC01_LIVE_CONFIRM=I_UNDERSTAND_REAL_MONEY`
5. CLI `--submit`
6. config `expected_account_number` equals `get_account().account_number`
7. the account is not `trading_blocked` or `account_blocked`, and its status is `ACTIVE`
8. the kill switch is off, in both the config and the ledger

Items 1 to 5 are checked before any broker client exists. Items 6 to 8 are checked on every live run, including a dry run, before reconciliation. A key that looks like the other mode's (`PK` for paper, `AK` for live) is refused.

## Steps

Run everything from the repository root so `.env` is found.

1. **Regenerate keys.** A key pair was pasted into a chat earlier, so treat it as compromised. In the Alpaca dashboard, regenerate the paper key on the paper account and the live key on the live account. Never paste keys into a chat, a ticket, or a commit.

2. **Fill `.env`** (gitignored). The repository has no `.env.example` file; copy these placeholders:

   ```text
   VEYTRIX_ENV=local
   DATABASE_URL=postgresql+psycopg://veytrix:local-dev-only@127.0.0.1:5433/veytrix
   ALPACA_PAPER_API_KEY=
   ALPACA_PAPER_SECRET_KEY=
   ALPACA_LIVE_API_KEY=
   ALPACA_LIVE_SECRET_KEY=
   # Only when you mean it:
   # MAC01_LIVE_CONFIRM=I_UNDERSTAND_REAL_MONEY
   ```

   Do not set `VEYTRIX_ENABLE_LIVE_BROKER`. The API and this runner both refuse to start if it is set.

3. **Migrate.**

   ```bash
   .venv/bin/alembic -c services/api/alembic.ini upgrade head
   ```

4. **Paper dry run.** This uses the shipped config (`mode: paper`, `submit_orders: false`). It places no order.

   ```bash
   .venv/bin/python -m veytrix_quant.mac01 run
   ```

5. **Paper submit.** Set `submit_orders: true` in `config/mac-01.yaml`, then run during regular hours:

   ```bash
   .venv/bin/python -m veytrix_quant.mac01 run --submit
   ```

6. **Live dry run.** Set `mode: live`. Copy your live account number from the dashboard into `expected_account_number: "..."`. Leave `live_enabled: false` and `submit_orders: false`. This checks the account and prints what it would do. It places no order.

   ```bash
   .venv/bin/python -m veytrix_quant.mac01 run
   ```

7. **Live submit.** Set `live_enabled: true` and `submit_orders: true`, and add `MAC01_LIVE_CONFIRM=I_UNDERSTAND_REAL_MONEY` to `.env`. Then run once, or schedule:

   ```bash
   .venv/bin/python -m veytrix_quant.mac01 run --submit
   .venv/bin/python -m veytrix_quant.mac01 schedule --submit
   ```

Controls:

```bash
.venv/bin/python -m veytrix_quant.mac01 status
.venv/bin/python -m veytrix_quant.mac01 pause
.venv/bin/python -m veytrix_quant.mac01 resume
.venv/bin/python -m veytrix_quant.mac01 kill-switch
.venv/bin/python -m veytrix_quant.mac01 kill-switch --release
.venv/bin/python -m veytrix_quant.mac01 backtest --fee 0 --spread-bps 2 --slippage-bps 5
```

The dashboard can pause, resume, and engage the kill switch. Only the command line can release the kill switch. Neither cancels an order that is already at Alpaca; cancel those in the Alpaca dashboard.

Exit codes: 0 ok, 1 error, 2 refused (config, credentials, or live gate), 3 blocked by a safety check or bad data, 4 another instance holds the Postgres advisory lock.

## Limits

- IEX daily closes can differ from the consolidated close. Use `data_feed: sip` only if your plan includes SIP.
- P&L uses broker-reported fills, FIFO, before fees and regulatory charges.
- The key-prefix check is a heuristic, not a guarantee. The account-number match is the real check.
- The backtest uses synthetic fixture bars. It is hypothetical and not a track record.
