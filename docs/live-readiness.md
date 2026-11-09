# Live readiness

Documentation only. Nothing in this file turns live trading, signing, broadcast, or a bank transfer on.

Prepared 9 November 2026 because the remaining-build work order asks for the list and says not to activate it.

| Item | State | What you would have to do later |
| --- | --- | --- |
| Account eligibility | Not reviewed | Confirm the broker account can trade the one strategy you intend to use. |
| Trust, benefits, and tax review | Not commissioned | A professional review before live funding or a withdrawal. The `$2,000` software cap is not that review. |
| Broker permissions | Not verified | Paper and live keys stay separate. The pair pasted in chat is compromised and must be revoked. |
| Live credential isolation | Not built as a deployment | The API still refuses `VEYTRIX_ENABLE_LIVE_BROKER`. The MAC-01 gate is unused. |
| Owner-signed risk budget | Not signed | `$100` notional and `$100` position are the current caps. They are not a signed budget for a live pilot. |
| First live order | Not authorised | Needs a separate written yes after the paper record. No live order has been sent. |
| Bank transfer | Not authorised | Manual approval only, after a broker-supported path exists. Do not store routing numbers here. |
| Incident plan | Local only | Pause and the MAC-01 kill switch exist on this machine. They do not cancel a resting Alpaca order, and there is no on-call rotation. |

`LIVE_TRADING_ENABLED`, `ONCHAIN_SIGNING_ENABLED`, `ONCHAIN_BROADCAST_ENABLED`, and `BANK_TRANSFER_ENABLED` stay false.
