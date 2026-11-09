# Market data

Two sources. Neither one submits an order.

## SAMPLE

Generated in memory from a fixed seed. Not written to `price_bars`.

| Field | Value |
| --- | --- |
| Symbol | `SAMPLE` |
| Venue | `SIM` |
| Asset type | equity |
| Currency | USD |
| Source id | `synthetic-sample` |

Weekday timestamps are UTC. Exchange holidays are not modelled. The `XNYS` calendar name is a label only. These bars are not a market price.

## Coinbase display

`veytrix_market/coinbase.py` reads the Coinbase Exchange public API for BTC-USD, ETH-USD, and SOL-USD. Daily candles, a short 1-minute window, and the last trade are for personal display on this machine. The series is not stored in git and not written to the database. If the request fails, the caller gets no invented price.

Source id: `coinbase-exchange`. This is not a consolidated quote, and it is not an order.
