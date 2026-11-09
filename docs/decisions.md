# Decisions

The accepted overrides are ADR 0002 (`docs/adr/0002-owner-overrides.md`). ADR 0001 still governs API boot. This note records how the 9 November 2026 work order sits on top of those decisions.

## Still in force

- MAC-01 buys stay at a `$100` notional and a `$100` position. The work order's one-share sentence is not the rule.
- The live gate stays unused. `VEYTRIX_ENABLE_LIVE_BROKER` still refuses to boot the API.
- Swaps stay simulated on Solana devnet, Ethereum Sepolia (`11155111`), and Base Sepolia (`84532`). No signing and no broadcast.
- The app stays on this machine. Supabase, AWS, a model provider, Apple distribution, and bank payouts stay blocked until the owner acts.
- There is no order route on the API. Agents cannot trade. `submit_orders` in `config/mac-01.yaml` stays false.

## Added for this work order, without spending or an order

- `FUTURES-01` exists as a disabled desk. Topstep automation stays off. That is a registry row and a read-only posture, not an execution path.
- `LIVE_TRADING_ENABLED`, `ONCHAIN_SIGNING_ENABLED`, `ONCHAIN_BROADCAST_ENABLED`, and `BANK_TRANSFER_ENABLED` stay false. They are not switches in this process.
- A `.env` file was not created. `.env.example` was not added in this pass because the editor refused that filename. Placeholders stay out of chat.

## Not decided here

Organisation, region, and cost for Supabase. A budget for AWS. Regenerated Alpaca keys and a written yes for the first paper submit. The Wednesday meeting time and DayPilot access. An Apple distribution path. A model account and the model ids it can call. A legal, tax, and benefits review before any payout or live funding.
