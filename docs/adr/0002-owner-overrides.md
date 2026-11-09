# ADR 0002: Owner overrides to the November 2026 master plan

## Status

Accepted 8 November 2026. Overrides parts of ADR 0001 and of master plan version 4.1.

## Context

The master plan assumes a Supabase project, AWS workers, a one-share AAPL order, read-only mainnet RPC for DeFi, and a 21st.dev-inspired Mission Control. The tree already has a local FastAPI app, a Coinbase display, a MAC-01 CLI, and a simulated swap CLI. The owner had already chosen different limits. Those choices are easy to "correct" by mistake if they live only in a chat.

## Decision

- MAC-01 buys use a `$100` notional cap and a `$100` position cap, with at most 2 orders a day. The plan's one-share rule is not the rule.
- The eight-condition live gate stays. No live order is placed until a separate authorisation. No paper order is placed until the owner regenerates the compromised Alpaca keys and authorises the first paper submit.
- Swaps stay simulated on Solana devnet, Ethereum Sepolia (`11155111`), and Base Sepolia (`84532`). The CLI does not sign or broadcast. Mainnet RPC is out. `contracts/` is not deployed.
- The app stays local. Do not provision AWS. Do not provision Supabase, and do not reuse the `nexgrail` or `gridlock` projects, until the owner approves an organisation, a region, and the cost.
- Keep the obsidian and jade dashboard. Do not copy the 21st.dev shell.
- The API process remains paper-only: it still refuses a non-local environment, a non-local database host, and `VEYTRIX_ENABLE_LIVE_BROKER`.

## Consequences

Phase 01 and Phase 12 of the master plan are blocked, not merely unscheduled. Phase 03 and Phase 05 cannot be called complete from unit tests. A future cloud design is a new ADR, not a silent edit to this one.

ADR 0001's boot rules for the API still hold. Its sentence "no broker client is a dependency" does not. alpaca-py is a MAC-01 dependency, imported only by the two adapter modules.

## Alternatives considered

Following the plan literally would replace a working local desk with cloud accounts the owner has not approved, and would shrink the order cap the owner already set. Copying the plan's one-share rule into `config/mac-01.yaml` was rejected.
