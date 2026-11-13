# Release checklist

Date: 13 November 2026. This list is the gate for a **paper-trading** release on this machine. Live trading is a separate gate at the bottom and is not approved.

Nothing in this list is ticked because a paper release happened. The ticks are evidence from the 13 November audit. A paper release is not ready.

Paper mode stays the default. `live_execution` stays false. Do not set `VEYTRIX_ENABLE_LIVE_BROKER` to a truthy value. Do not add an order route to the API.

## Paper release — current evidence

| Gate | State | Evidence |
| --- | --- | --- |
| App binds to loopback only | Met for the processes that are up | Vite `127.0.0.1:5173`, API `127.0.0.1:8000`, Postgres `127.0.0.1:5433` |
| `VEYTRIX_ENV` is `local` | Met | Diagnostics `env` `local`. Any other value refuses boot. |
| Live broker flag does not enable live | Met for the running process | Diagnostics `live_broker` `disabled`. The variable is SET in that process; the value was not printed. A truthy value would have refused boot. |
| API cannot submit an order | Met | `order_route` `absent`, `execution_permitted` false, `api_reaches_engine` false. `POST /api/v1/risk/size` is a calculator. |
| MAC-01 stays off the HTTP path | Met | Only the CLI may call `Mac01Engine.run`. No LLM, chat, or road can reach it. |
| Paper is the MAC-01 default | Met in config | `config_mode` `paper`, `config_submit_orders` false, `config_live_enabled` false. |
| Eight live conditions are all unmet | Met | `conditions_met` 0. This is evidence, not a reason to meet them. |
| Registry cannot trade | Met on the live read | All 10 desks: `can_submit_orders`, `can_sign`, `can_transfer_funds`, `holds_credentials` false. `status` `enabled` is paper research only. |
| Comms cannot turn on live execution | Met | `live_execution` false and not a setting. |
| Model output cannot place an order | Met because there is no model | `model` `not_configured`. Replies are not `model_generated`. |
| Topstep stays disconnected | Met | `topstep_account` `not_connected`, automation `disabled`. |
| Swaps cannot sign | Met by design | Paper-swap CLI refuses a private key. API has no swap submit route. |
| No secret in the frontend bundle path | Met for the running Vite process | `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, and `VITE_API_BASE_URL` were unset. No `.env` file in either tree. |
| Auth and CSRF | Not met, and not claimed | `auth` `not_configured`, `csrf` `not_implemented`. Safe only while the process stays local. |
| Alpaca paper account connected | Not met | Paper key variables unset in the API process and in this shell. No paper order has been sent by this build. |
| Broker reconciliation | Not met | Local ledger only. A stored broker id is not a match. |
| Independent Aegis approval of a paper order | Not met | Previews withhold release. There is no approval gateway in front of a broker. |
| Scheduler running a paper session | Not met | Schedule route reports a clock. It cannot start a run. |
| 30 days of paper evidence | Not met | No paper fills. |
| Tests green on the branch that will ship | Not met | `bash scripts/check.sh` exit 1. Two registry tests fail against the live database. See the baseline report. |
| Preview sky view committed and reviewed | Not met | Uncommitted files remain on `feature/agent-communication`. This checklist commit does not include them. |
| Staging environment | Not met | Does not exist. Non-local boot is refused. |
| Backups and restore drill | Not met | Not run. |
| Owner written approval for one paper submit | Not met | Required before any `--submit`, even on paper. |

## Before anyone calls paper "released"

1. Merge or otherwise keep the preview sky view. Do not drop the uncommitted speech, feed, and walk behaviour.
2. Decide where migration `0012` lives, and make the branch under test agree with the database. Do not weaken `tests/test_agents_api.py` to hide `status = enabled`.
3. `bash scripts/check.sh` exits 0 on that branch.
4. Regenerate Alpaca paper keys outside chat. Store them only in a gitignored local file. Confirm the API process still does not read them.
5. One supervised paper submit, only after you say so in writing. Capture the broker id. Reconciliation may say confirmed only for that acknowledgement.
6. Kill switch, stale-data stop, and the $100 caps still hold. Long only. No short, no leverage, no options.
7. Diagnostics still show `auth` `not_configured` until auth exists, and the release stays on loopback until that changes.

## Live trading — separate, not approved

Do not treat a green paper checklist as permission to trade real money.

All of the following would be required later, and none of them is done:

- A separate written approval from you.
- Independent review of the live gate (`docs/reviews/PENDING.md` item 11).
- `mode: live`, `live_enabled: true`, `submit_orders: true`, `MAC01_LIVE_CONFIRM`, `--submit`, a matching `expected_account_number`, an unblocked `ACTIVE` account, and the kill switch off. Each one already has a test. Meeting them is not authorised.
- Caps that stay at $100 notional, $100 position, 2 orders a day, one open order, long only, until you change them in writing.
- Live keys that are not the paper keys.
- The API still refuses `VEYTRIX_ENABLE_LIVE_BROKER` and still has no order route.
- No agent, chat message, or road can set those conditions.

Current live evidence: `live_submission_possible` false. No live order has been placed by this build.
