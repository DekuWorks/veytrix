# Activation report — 13 November 2026

Branch `feature/sprint-0-stabilization` in `/Users/marcusbrown/Developer/veytrix-sanctum-preview`. Not pushed.

Recovery commit: `8f6c6aa470e673cf0b1ba896c0e3ce946ce295a0`.
Worker commit: `b329141`.
Alembic on `127.0.0.1:5433`: `0014_worker_tasks`. Port 5432 was not used. The database was not reset.

This is not a completed research activation. Checks 3, 4, and 11 failed for the reasons below.

## What is running

| Service | Address or pid | Notes |
| --- | --- | --- |
| API | `127.0.0.1:8000`, pid 74425 | Restarted once from pid 55701. `VEYTRIX_ENABLE_LIVE_BROKER=0`. Ready, database up. |
| Vite | `127.0.0.1:5173`, pid 52596 | Existing process, not a second server. |
| Research worker | pid 74192 | `launchd` label `com.veytrix.research-worker`, `KeepAlive` true. Script `scripts/run-research-worker.sh`. |

The five-minute proof used pid 65593. `ps` showed elapsed `05:15` and `private.agent_presence` had 10 of 10 heartbeats newer than 30 seconds. Stopping that pid caused launchd to start pid 74192. Heartbeats were fresh again after the replacement. Presence stays offline only after the heartbeat is older than 30 seconds.

## Checks

1. Pass. Roads answered “What are you working on?” with origin `model_generated`, model `claude-haiku-4-5-20251001`, provider message id `msg_011Ch1gfKTB4dcsNaXnmUoDN`, 273 input tokens and 44 output tokens. Message `940aae4c-439e-4be6-a45e-b399d9e39125`. Eighteen chunks arrived before `done`.
2. Pass. “coordinate an NVIDIA research review” stored an assignment from `SUPERVISOR-01` and queued `RESEARCH-01` and `DEFI-01`.
3. Fail. Astra `0647909f-77d0-4a0e-b984-e3b2beaf3ade` and Cipher `a7e918aa-7ce6-407a-a145-b31508e0caac` are `blocked` / `no_stored_source`. Their model replies say there is no stored source. That is honest, and it is not an evidence-backed finding. Provider ids `msg_011Ch1gftX1em9ohiVS6atiN` and `msg_011Ch1gfwycqceCQizb6U3aG`.
4. Fail. Aegis `991a3754-ea23-46f4-8013-d8a79b7757de` is `blocked` / `no_findings`. The stored line is `scripted`, not a review of findings: “The limitation is that there is no verified market finding.”
5. Pass. Roads summary is origin `tool_verified`: “NVIDIA review. Verified findings: none. Blocked or failed: Cipher (blocked), Astra (blocked).”
6. Pass. Worker pid 65593 was still the same process at 5 minutes 15 seconds, with 10 fresh heartbeats.
7. Pass. The queued NVIDIA rows moved to `blocked` while the worker process ran. The browser was not used for that step.
8. Pass. Sky View’s activity feed showed “Verified findings” and “no stored source” after reload. The floor layout was not replaced.
9. Pass. The floor showed “DEFI-01 · NVIDIA is blocked” and “RISK-01 · NVIDIA is blocked”, each with Acknowledge.
10. Pass. After the API restart, the three task ids above were still `blocked`. `mac01_orders` was 0 and `paper_positions` was 0.
11. Fail. `ALPACA_PAPER_API_KEY` and `ALPACA_PAPER_SECRET_KEY` are absent from the local `.env`. No paper read was attempted and no order was submitted.
12. Pass. Live broker stayed off. The Roads response had `execution_permitted` false and `order_submitted` false. Order tables stayed at 0.

## Tests this pass

| Check | Result |
| --- | --- |
| `ruff check` | Passed |
| `pytest` | 457 passed, 0 failed, 0 skipped |
| `npm --prefix apps/web run typecheck` | Passed |
| `npm --prefix apps/web test` | 47 files, 288 passed |
| `npm --prefix apps/web run build` | Passed |
| `scripts/scan_secrets.py` | No findings |

The key was unset for pytest. One Roads stream and two specialist model calls were made outside the suite, after the suite, with the real key. The key was not printed.

## Blockers that need the user

- Alpaca paper credentials are not in the local environment. A paper read or a paper order cannot proceed. An order also needs explicit owner approval, which this run did not have.
- There is no stored NVIDIA note or source event, so research cannot be completed without inventing a source.
- Authentication is not implemented. The API remains bound to `127.0.0.1`. No founder login was added.
- Supabase Realtime is not configured. The feed says so.

## Not claimed

Claude is connected for the calls above. The NVIDIA research workflow did not produce evidence-backed findings. Live trading is disabled.

## Paper desk activation

Branch `feature/paper-desk-activation` in this worktree, based on `b30d292`. Not pushed. Alembic on `127.0.0.1:5433` is `0015_desk_runs`. Port 5432 was not used.

CRYPTO-01 is the only desk marked `active`. A live cycle read Coinbase daily candles, source `coinbase-exchange`, bar start `2026-11-13T00:00:00+00:00`. The close did not rise against the previous candle, so the rule wrote no fill. `paper_fills` stayed at 0 and `mac01_orders` stayed at 0. `VEYTRIX_ENABLE_LIVE_BROKER` stayed false. A unit cycle with a rising pair wrote one `BTC-USD` fill and a second cycle did not add another. That fill has `execution_permitted` false and `order_submitted` false.

STOCK-01 and ETF-01 are `idle` with source `synthetic-sample` and reason `alpaca_market_data_absent`. They are not active. FUTURES-01 is `blocked` / `market_data_not_read`. DEFI-01 is `blocked` / `no_fresh_quote`. YIELD, NFT, TAX-LIEN, and LAND are `blocked` / `no_provider`. They are not registry desks and they have no prices.

Acknowledging an alert inserts `private.alert_acks` and leaves the research task `blocked`. TraderPost and SignalStack adapters default to `rejected_disabled`. One selected route rejects the other provider. A valid payload is still `rejected_broker`. Market Gear and the Alpaca CLI are documented only. The CLI is not invoked.

The market page already plots Coinbase candles with Lightweight Charts. SAMPLE stays labelled synthetic.

Obsidian search and edit confirmation live in `apps/obsidian-assistant` and do not open a port. The Grok module in `apps/grok-assistant` keeps tenants apart, rate-limits, and does not call xAI or import trading code.

| Check | Result |
| --- | --- |
| `npm --prefix apps/web ci` | PASS |
| `npm --prefix apps/web run typecheck` | PASS |
| `npm --prefix apps/web test` | PASS, 288 tests |
| `npm --prefix apps/web run build` | PASS |
| `ruff check` and `pytest` | PASS, 466 tests |
| `scripts/scan_secrets.py` | PASS, no findings |
| `node --test apps/obsidian-assistant/vault.test.mjs` | PASS, 3 tests |
| Paper soak on the scratch database | PASS, one fill then no duplicate, ack leaves the task blocked |
| Live Coinbase cycle | PASS for a fresh read. No fill, because the close did not rise |
| Alpaca paper read | BLOCKED, paper keys are absent |
| YIELD, NFT, tax liens, land | BLOCKED, `no_provider` |
| Broker order | Not sent |

This is not 100 percent complete. Stock, ETF, futures, and DeFi desks have no fresh feed. No live-money order was sent.
