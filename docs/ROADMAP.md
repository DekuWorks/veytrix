# Roadmap

The numbers in the table below are the original sprint-0 sequence. They are not the phases in the November 2026 master plan. Delivery status for that plan is `docs/implementation-checklist.md`. Dates are not commitments.

Several rows below are overtaken by work already in the tree: Coinbase display, the MAC-01 CLI, and simulated testnet swaps. AWS and a live broker flag that boots are still out. See ADR 0002.

| Phase | Status | Intent |
| --- | --- | --- |
| 0. Foundation | In this branch | Shell, health, SAMPLE, Coinbase display, paper sizing, local Postgres, CI. No commits yet |
| 1. Still paper | Not started | Auth gateway design, session threat model, and a written CSRF approach before any cookie |
| 2. Audit writes | Partial | Size journal exists. Daily and weekly stops are still not enforced |
| 3. Public data | Partial | Coinbase BTC-USD, ETH-USD, and SOL-USD for display. SEC EDGAR is not started |
| 4. Event notes | Partial | Local source-event rows. A score still cannot place a trade |
| 5. Quant sandbox | Partial | MAC-01 CLI, AAPL SMA 20/50, $100 cap. No order from the API |
| 6. Paper ledger | Partial | MAC-01 ledger and simulated swap rows. Sizing stops are still not enforced |
| 7. Research assistant | Not started | No model provider, no execution tool, and no withdrawal tool |
| 8. God's Eye audit | Not started | Fork the pinned commit, then separate MIT code from non-MIT data |
| 9. Paper simulator | Partial | Simulated testnet swaps. A simulator is still not a broker |
| 10. External review | Not started | Independent pass over the threat model and the supply chain. Codex has not run |
| 11. Operational hardening | Not started | Backups, log retention, and dependency update policy for the private machine |

Live brokerage is not one of these phases. It would require a separate decision. Even then, an agent must not hold withdrawal permission, and model output must not submit orders.

Phase numbers here are planning labels. They are not a promise that each one will be built.
