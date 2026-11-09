# Production readiness

Date: 9 November 2026. Result: **FAIL**. Paper production is not deployed, not observed with the developer machine off, and not reconciled to Alpaca. This file does not authorise live trading.

| Gate | Result | Evidence |
| --- | --- | --- |
| Local API boot rules | PASS for the local process only | API refuses a non-local env, a non-local database host, and `VEYTRIX_ENABLE_LIVE_BROKER`. |
| Auth, RLS as an owner login, MFA | FAIL | Authentication is not implemented. The API role bypasses row security. |
| Alpaca paper read and one paper order | FAIL | No credentials in the tree. No broker call this pass. No broker order id. |
| Shield release | FAIL | Previews withhold release. Buying power is not read. |
| 30-day paper record | FAIL | The clock has not started. |
| Codex review | FAIL | `codex` is not on `PATH`. `docs/reviews/PENDING.md` is awaiting review. |
| Payout and bank transfer | FAIL | `BANK_TRANSFER_ENABLED` stays false. No transfer route. |
| Always-on workers | FAIL | The app stops when this machine stops. AWS was not provisioned. |

Screenshots and broker ids are absent because those checks were not run. Do not treat a green local `scripts/check.sh` as this gate.
