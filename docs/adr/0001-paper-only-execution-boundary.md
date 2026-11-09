# ADR 0001: Paper-only execution boundary

## Status

Accepted for the API process on 7 November 2026. Superseded in part on 8 November 2026 by [ADR 0002](0002-owner-overrides.md).

The boot rules below still hold. The sentence "no broker client is a dependency" does not: alpaca-py is a dependency of the MAC-01 command line only. Public Coinbase display data also exists. The API still does not submit an order.

## Context

Veytrix is a personal research app. The useful part is looking at information and trying a position-size calculation. The dangerous part would be a path from that calculation, or from a model, to a broker.

The sizing formula is experimental. Stops can fail. A daily or weekly loss figure that is only stored in a table is not a control.

## Decision

- The API boots only for `VEYTRIX_ENV=local`, with live broker mode off, and a local database host.
- `POST /api/v1/risk/size` returns a share count and the constants `execution_permitted=false` and `order_submitted=false`.
- No broker, exchange, wallet, or bank client is a dependency.
- Sample prices are synthetic and labelled. They are not written into `price_bars`.
- Daily and weekly stops are stored on the seeded policy and are not applied, because there is no ledger.
- Agents must not be given withdrawal permissions in any later design.

## Consequences

The app can be used on one machine without a brokerage account. It cannot be pointed at a server and called safe: authentication is absent, so the loopback bind is doing the access control.

A future paper ledger can enforce the stored stops only after that ledger exists and the enforcement is tested. Flipping a boolean on the current row is blocked by a database check and by the policy object.

Adding a live broker later is a new decision, not an extension of this one.

## Alternatives considered

A paper-trading SDK behind a feature flag was rejected. Flags get turned on. A fake broker object was also rejected, because it becomes the place a live adapter gets attached.
