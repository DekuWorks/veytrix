# Target state

This is the delivery target after the 8 November 2026 audit. It keeps the safety rules in `CLAUDE.md` and the owner's decisions where they disagree with `VEYTRIX_CURSOR_CODEX_MASTER_BUILD.md` version 4.1. The plan file in Downloads was not edited.

## Decisions that override the plan

| Topic | Plan text | What stands |
| --- | --- | --- |
| AAPL size | Phase 05: maximum one share per signal | `$100` notional per buy and `$100` position. Already in `config/mac-01.yaml`. A sell still closes the whole held quantity. |
| Live trading | Phase 13 live pilot after a paper record | The eight-condition live gate stays in the CLI. It is unused. No live order is authorised. |
| Swaps | Phase 07 also asks for read-only mainnet RPC | Simulated fills only, on Solana devnet, Ethereum Sepolia (`11155111`), and Base Sepolia (`84532`). No signing, no broadcast, no mainnet. `contracts/` stays unaudited reference code. |
| Hosting | Phase 01 Supabase plus Phase 12 AWS workers, and "do this now" step 7 | The app stays on this machine. No AWS. No Veytrix Supabase project until the owner picks an organisation, a region, and a cost, in writing. The `nexgrail` and `gridlock` Supabase stacks are not available for this. |
| Dashboard kit | Phase 08: 21st.dev-inspired components where the licence allows | Keep the obsidian and jade shell. Do not vendor the 21st.dev Dashboard Shell. |
| First paper order | Phase 03 smoke test and Phase 05 autonomous paper | Blocked until the owner regenerates Alpaca keys and separately authorises one paper submit. |
| Roadmap numbers | `docs/ROADMAP.md` phases 0–11 | Those numbers are the old sprint-0 list. Delivery status is `docs/implementation-checklist.md`. |

## What local paper production means here

Until the owner reverses the hosting decision, "done" does not include a Supabase project, an AWS account, or a laptop-off worker.

A later local paper desk, if the owner asks for it, would still have to show:

- the existing Coinbase display for BTC-USD, ETH-USD, and SOL-USD, still labelled as a personal display that sends no order
- the synthetic SAMPLE series still labelled synthetic
- MAC-01 paper orders only after the authorisation above, with broker-returned ids stored, and the $100 caps held
- simulated swap receipts labelled simulated
- the API still refusing to boot outside `VEYTRIX_ENV=local` and a local database host
- no order route on the API, and no path from a model or a web page to `Mac01Engine.run` or the swap CLI
- authentication designed and reviewed before any cookie exists

## Pros and cons of staying local

Pros: no cloud bill, the boot check matches how the app is actually used, and a missing auth gateway is not exposed on the internet. The Coinbase display and the paper calculators already work on loopback.

Cons: the MAC-01 schedule stops when the laptop sleeps, so it is not the plan's always-on paper worker. There is no off-site backup test. Loopback is not a login. Supabase Auth, RLS, and an iOS push path are unavailable until the owner accepts that cost and a new threat model.

## Explicitly not the target

- Treating a simulated swap, a SAMPLE bar, or an empty ledger as proof of an Alpaca fill.
- Enabling live orders, shorts, leverage, options, wallet signing, or bank transfers as part of paper work.
- Reusing another project's Supabase keys or the compromised Alpaca key.
- Claiming a weekly profit. The plan forbids that, and so does this repo.
