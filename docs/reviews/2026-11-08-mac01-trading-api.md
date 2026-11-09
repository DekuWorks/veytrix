# MAC-01 on the Alpaca Trading API: self-review and test report

Author: Cursor agent, 8 November 2026. This is the implementer's own review. It is not independent. Claude Code has not reviewed it, and Codex did not write or run these tests. The independent review is `PENDING.md` item 11.

## What changed

- The Broker API sandbox adapter (httpx) was replaced with alpaca-py `TradingClient` (`paper=True` or `paper=False`) and `StockHistoricalDataClient` (`Adjustment.ALL`, IEX unless the config says SIP).
- Config: `mode: paper | live` (default paper), `live_enabled`, `expected_account_number`, and Decimal caps `max_notional_per_trade` and `max_position_notional` (both at most 100.00), plus `max_orders_per_day` (at most 2).
- Live gate: five static conditions are checked before any broker client exists; three runtime conditions are checked on every live run.
- Sizing: a buy is a notional market DAY order, rounded down to cents. A sell is a market DAY order for the whole held quantity.
- Schedule: 09:35 New York on Alpaca trading days. Submission is blocked outside 09:30 to 15:45 of the session after the signal session.
- Ledger: the `0007` migration was edited in place, because it had not been applied to the local database (still `0006`). It now has a `mode` column, a nullable `notional` and `qty`, and a sizing check (`buy` has notional at most 100 and no qty; `sell` has qty and no notional).
- The API's MAC01 Broker-sandbox boot refusals were removed. The three original refusals are unchanged. The API still imports no broker client and has no submit route.

## Findings from the Alpaca docs

- Notional and fractional orders are supported for market, limit, stop, and stop-limit orders with `time_in_force=day`. Notional allows at most two decimal places; extra decimals are rejected. Fractional sells are always marked long. Check the asset is fractionable. Source: [Alpaca, n.d.-a](https://docs.alpaca.markets/docs/fractional-trading).
- Fractional market orders fill only in regular hours. Extended hours need a limit order with `extended_hours=true`. Source: [Alpaca, n.d.-a](https://docs.alpaca.markets/docs/fractional-trading); [Alpaca, n.d.-b](https://docs.alpaca.markets/docs/orders-at-alpaca).
- DAY orders submitted after the close are queued for the next trading day. Notional orders cannot be replaced. A new notional order cannot open while closing-position orders are open. Source: [Alpaca, n.d.-b](https://docs.alpaca.markets/docs/orders-at-alpaca).
- Conclusion: a notional market DAY buy belongs in regular hours, so the run is at 09:35 New York on trading days, using the previous completed session's bar.

## alpaca-py behaviour that needed code (version 0.45.0)

- `RESTClient` calls `requests` with no timeout. The adapter wraps the session and sets 10 seconds.
- It retries 429 and 504 responses, including on `POST /v2/orders`, and ignores `retry_attempts=0`. The adapter sets `_retry = 0`. A test asserts a 429 submit is sent once.
- The dependency is pinned to `>=0.45,<0.46` because the hardening touches private attributes.

## Tests

- pytest (excluding the other worker's `tests/test_swapbot*`): see the final report for counts.
- Live gate: each static condition is tested alone in the engine and in the CLI (the CLI refuses before any client or database). The runtime conditions tested are account mismatch, empty account number, `trading_blocked`, `account_blocked`, non-ACTIVE status, lookup failure, and the ledger kill switch. All conditions together submit once.
- Mutation check: disabling the account-number comparison, or the confirm-phrase comparison, makes those tests fail.
- Secrets: `capsys` and `caplog` show no key or secret in output, structured logs, the run reason, or the ledger. `repr` of the adapters and of `TradingEnvironment` hides them.

## Open risks

- IEX closes can differ from the consolidated close, so a crossover on IEX may not match SIP.
- The `PK`/`AK` key-prefix check is a heuristic. The account-number match is the real guard.
- P&L excludes fees and regulatory charges.
- A manual order placed outside MAC-01 blocks the bot (one open order at a time) until it is resolved.
- No paper or live call has been made from this tree; there is no `.env` with keys.

## References

Alpaca. (n.d.-a). *Fractional trading*. https://docs.alpaca.markets/docs/fractional-trading

Alpaca. (n.d.-b). *Orders at Alpaca*. https://docs.alpaca.markets/docs/orders-at-alpaca
