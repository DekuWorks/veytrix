# Implementation status

Date: 13 November 2026. Branch: `feature/phase-0-reconnaissance`. The audit commit was `7090490`. A later commit on the same branch adds the runtime-mode seam described below. The live worktree `feature/agent-communication` at `86e9d7d` still has uncommitted files. Phases 1–10 were not rebuilt.

## Latest increment

The registry read path accepts `status` `enabled` as well as `disabled` and `paused`. Trading flags stay false. No Alembic revision was added or applied, because the live database is already at the preview's `0012` and this branch does not contain `0011`. F1 Skyview was not started: it lives on the other branch, and merging the two trees was not part of this change.

The earlier runtime seam is unchanged: `VEYTRIX_MODE` defaults to `development`, live mode refuses to boot, and the provider posture stays simulated or disconnected. Claude, Supabase, and Alpaca were not called. YIELD was not inserted. `FUTURES-01` was not removed. Vite and the API were not restarted.

Read `docs/ARCHITECTURE.md` for the two trees. Read `docs/MASTER_BUILD_PLAN.md` for task-level status. Nothing below is a claim that paper trading is in production.

Confidence: high for HTTP checks and files opened. Medium where the note says the browser was not used. The preview's uncommitted diff was inspected with `git diff --stat` and by reading the files named here. It was not committed.

## Canonical

| Question | Answer |
| --- | --- |
| Repository | One repo. Preview is a linked worktree of `/Users/marcusbrown/Developer/veytrix`. |
| Running sky view | Preview worktree. Vite `127.0.0.1:5173`. Do not discard it. |
| This commit | Main checkout, `feature/phase-0-reconnaissance`. It does not contain the sky-view commits. |
| Database | `veytrix-local-postgres` on `127.0.0.1:5433`. Alembic `0012_enable_registry_status`. Port 5432 is `daypilot-db`. |

## Working

These responded or are present in the running preview. "Working" means the behaviour described, not that the phase is finished.

| Surface | Evidence this pass | Limit |
| --- | --- | --- |
| API liveness and database | `GET /api/v1/health` 200, `GET /api/v1/ready` 200, `database` `up` | Local only |
| Paper posture | Diagnostics: `trading_mode` `paper`, `live_broker` `disabled`, `execution_permitted` false | Auth is `not_configured` |
| Live submission evidence | `GET /api/v1/system/submission`: 0 of 8 conditions met, `live_submission_possible` false, `order_route` `absent` | Does not read the broker account |
| Registry for paper research | Live `GET /api/v1/agents`: 10 desks, `status` `enabled`, all four trading flags false | This branch now accepts `enabled` on read. Trading flags stay false. No new migration was applied. The running API process was not restarted. |
| Comms flags | `GET /api/v1/comms/flags`: chat flags on, `live_execution` false, `model` `not_configured`, `realtime` `not_configured` | Replies are not a model |
| Inference posture | `paid_inference_enabled` false, Cursor does not run agents, Ollama off | `POST /api/v1/inference/route` was not called. The new mock seam is a different route and is not on the running process. |
| Sky view page | Preview `SanctumPage.tsx` renders `SkyFloor` (HTML/CSS). Vite returned HTTP 200. | Browser was not driven. Not React Three Fiber. |
| Speech bubbles and feed | Preview CSS: `.thought.live.overlay` fades in about 5.4s; `.sx-feed` scrolls. Chat panel source is present. | Not re-checked by clicking |
| Roads and Dayvid | Preview `SkyFloor.tsx` and `SkyFloor.test.tsx` keep both off the table and move Dayvid. Uncommitted. | Tests in the preview were not run this pass |
| North-wall sign | `SkyFloor.tsx` renders VEYTRIX SANCTUM | The letter V on that sign is the sign, not a table mark |
| MAC-01 rule | `services/quant`: AAPL SMA 20/50, long only, CLI only, paper default | Not EMA. No keys. No order sent. |
| Coinbase and SAMPLE routes | Present on the live OpenAPI | Coinbase was not called this pass. SAMPLE is synthetic. |
| Local checks that do not read `status` | Ruff clean. Pytest 319 passed, 1 skipped, 2 failed. Web typecheck clean. Vitest 237 passed. Web build succeeded. Secret scan clean. | Failures are real. See the baseline report. |

## Mock or labelled stand-in

| Item | What it actually is |
| --- | --- |
| SAMPLE bars | Generated in memory. Not a market price. |
| Comms replies | `tool_verified`, `scripted`, or `simulated`. Origin `model_generated` is a schema value and is not written. No Anthropic client. The new mock reply is also `simulated`, and it is not stored in the comms tables. |
| Inference router | Returns a refusal or a local decision. Opens no network connection to a model. |
| Supabase | `@supabase/supabase-js` is a web dependency. Live flags say `realtime` `not_configured`. Polling is the path. |
| Phaser floor | Still in `apps/web/src/sanctum/game.ts` and still what this branch's page mounts. The running page does not mount it. |
| Treasury monthly summary | A projection of caller-supplied or local figures. `transfer_status` stays `not_attempted`. |
| Shield and reservation previews | Arithmetic. Release stays withheld. |
| Futures posture | Constants: Topstep `not_connected`, automation `disabled`, desk status `disabled`. No Topstep call. |
| MAC-01 reconciliation | Local ledger. Broker read stays absent, so rows are not broker-confirmed. |
| Paper swaps | Simulated testnet ledger. Signing is absent. |
| Activity lines | Built from local posture and logs. They are not a verified fill feed. |

## Broken or inconsistent

| Item | What happens |
| --- | --- |
| Registry migration drift | This branch's Alembic files still stop at `0010`, which creates `status IN ('disabled', 'paused')`. The live database is already at the preview's uncommitted `0012`, which allows `enabled`. This branch did not add or apply another revision, so a fresh upgrade of this branch alone still seeds `disabled`. The API accepts both. |
| Registry versus futures posture | Agents row for `FUTURES-01` is `enabled`. `GET /api/v1/futures/posture` still says `status` `disabled` and Topstep `not_connected`. Both can be true only because the posture is hardcoded. |
| Two branches, one database | The database is at uncommitted migration `0012`. This branch's files stop at `0010`. The preview branch's last commit is `0011` plus the untracked `0012` file. |
| `scripts/check.sh` | Exit 1 at pytest. Ruff had already passed. Web typecheck, Vitest, build, and the secret scan were run afterwards, separately, and passed. |
| GitHub Actions | `.github/workflows/ci.yml` exists. It was not run on this commit. Actions tags are not pinned to SHAs. |
| Auth | Not implemented. CSRF is not implemented. Rate limit is process-local. |
| Persona names | Preview assigns Astra to `RESEARCH-01` and Dayvid to `DAY-01`. `docs/phase-0/agent-roster.md` still says those codes are unassigned. YIELD does not exist. |

`enabled` means paper research. It does not set `can_submit_orders`, `can_sign`, `can_transfer_funds`, or `holds_credentials`. A row that sets any of those still returns 503. Futures posture stays `disabled` and Topstep stays `not_connected`. The process on port 8000 was not restarted, so it still runs the preview code.

## Missing

| Item | Phase in the plan |
| --- | --- |
| React Three Fiber, Three.js, elevator, floors F2–F9 and B1 | 2 and 4 |
| Claude / Anthropic adapter, model key, prompts, heartbeats, pgvector memory | 3 |
| YIELD identity, Daniel view, COO role | 3, 4, 9 |
| Supabase project, Auth, Realtime channels that actually connect | 1 and 5 |
| Redis or any durable queue, outbox, dead-letter handling | 1 |
| Staging and production environments, AWS, HTTPS deployment | 1 and 10 |
| Alpaca paper keys, a paper order, broker reconciliation, EMA 20/50 | 6 and 7 |
| Quiver Quant, TradingView alerts, backtest with fees as a research product | 6 |
| Double-entry ledger, payout approval, bank movement | 8 |
| Member portal, invitations, RBAC that the API enforces | 9 |
| DayPilot, WhatsApp, Apple app | Not in this 0–10 map as a built feature. DayPilot stays absent. |

## Environment names

No `.env` file was found in either tree. Values were not printed. Presence:

| Where | SET | unset |
| --- | --- | --- |
| This shell | none of the names below | all of them |
| Vite process | none of the names below | all of them |
| API process | `VEYTRIX_ENV`, `VEYTRIX_ENABLE_LIVE_BROKER`, `DATABASE_URL` | the rest of the names below |

Names checked: `VEYTRIX_ENV`, `VEYTRIX_ENABLE_LIVE_BROKER`, `DATABASE_URL`, `VEYTRIX_RATE_LIMIT_PER_MINUTE`, `VEYTRIX_LOG_LEVEL`, `MAC01_LIVE_CONFIRM`, `ALPACA_PAPER_API_KEY`, `ALPACA_PAPER_SECRET_KEY`, `ALPACA_LIVE_API_KEY`, `ALPACA_LIVE_SECRET_KEY`, `SOLANA_DEVNET_RPC_URL`, `ETHEREUM_SEPOLIA_RPC_URL`, `BASE_SEPOLIA_RPC_URL`, `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `POSTGRES_PASSWORD`, `SWAPBOT_RPC_URL`, `SWAPBOT_PRIVATE_KEY`, `SWAPBOT_VARIANT`, `SEPOLIA_RPC_URL`, `MAINNET_RPC_URL`, `CI`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_URL`, `REDIS_URL`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `TOPSTEP_API_KEY`, `TWILIO_AUTH_TOKEN`, `WHATSAPP_TOKEN`.

`VEYTRIX_ENABLE_LIVE_BROKER` is SET in the API process and diagnostics still say `live_broker` `disabled`. A truthy value refuses boot. The value was not read for this note. Do not paste a replacement into chat.

`VITE_` names are unset, which matches "no API key in the frontend" for the running Vite process. The code still must not gain one.

## Preview dirty tree, left untouched

27 modified files and 2 untracked files on `feature/agent-communication`. Untracked: migration `0012` (already applied to the local database) and `services/api/veytrix_api/comms/work.py`. Modified areas include `SkyFloor`, speech, the chat panel, comms replies, and agent tests. This pass did not commit them and did not revert them.

## Blockers that need you

Do not paste secrets into chat.

| Blocker | Why it stops later phases |
| --- | --- |
| Alpaca paper key | Phase 7 cannot connect. The pair that was pasted in an earlier chat is compromised and has to be regenerated in the Alpaca dashboard, then stored locally, not in git and not in chat. |
| Supabase project | Phases 1 and 5. Needs an organisation, region, and a cost you accept. The nexgrail, gridlock, and avyro stacks on this machine are not Veytrix. |
| Model provider | Phase 3. No Anthropic key is set. A Cursor subscription does not call the production adapter, because there is no adapter. |
| Live trading | Separate written approval. The eight-condition gate is not that approval. `docs/reviews/PENDING.md` item 11 is still an open review. |
| YIELD versus `FUTURES-01` | The mission names YIELD. The repo has `FUTURES-01`. No code was added to resolve that. |
| Astra / Dayvid codes | Preview already displays a pairing. The Phase 0 roster doc does not. Confirm before a migration renames anyone. |
