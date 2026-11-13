# Master build plan

Date: 13 November 2026. Source: the Sanctum mission given that day (phases 0–10). This file is the plan. It is not a claim that the plan was built.

Phase 0 is the audit, these documents, and one baseline report (`docs/reviews/phase-0-sanctum-baseline-2026-11-13.md`). Phases 1–10 were not implemented in that pass. A status of `partial` means older code already covers some of the task. It does not mean this pass finished it.

Older plans use different numbers. `docs/implementation-checklist.md` is phases 00–13 from a November v4.1 brief. `docs/phase-0/reconnaissance.md` follows a Downloads task file numbered 0–12. Do not mix those numbers with the rows below.

Status words: `done`, `partial`, `not-started`.

Dependencies are "what must be true first". A blocked row stays blocked until the owner supplies the missing account or written approval. Do not paste secrets into chat.

## Order

```text
0 audit and protection
    → 1 core infrastructure
        → 2 F1 sky view (React Three Fiber is the target; today is HTML/CSS)
        → 3 Claude runtime (needs a model account; Cursor is not that account)
        → 5 realtime (needs Supabase, and auth from phase 1)
        → 6 market intelligence
            → 7 paper trading and MAC-01 (Alpaca paper keys; live stays off)
                → 8 treasury (no payout without a separate approval)
    → 4 floors F2–F9 and B1 (after the sky view exists; data from 3, 6, 7, 8)
    → 9 member portal (after auth)
    → 10 deployment (after the paper gates in docs/RELEASE_CHECKLIST.md)
```

Phase 4 can start as empty rooms only after phase 2 has a real floor switch. Filling a floor with broker or model data waits on the phase that owns that data.

## Phase 0 — Repository audit and project protection

Goal: know what is running, write it down, and keep the running sky view. Done when the four docs exist, the baseline report exists, and no preview file was reverted.

| Task | Status | Depends on | Acceptance |
| --- | --- | --- | --- |
| Inventory repository, apps, services, dependencies, branches, and deployments | done | none | `docs/ARCHITECTURE.md` (this volume: `docs/architecture.md`) names both trees, the listeners, and the dependency set. No secret value is in the doc. |
| Identify working sky view, floor, agent, market, and trading features | done | inventory | `docs/IMPLEMENTATION_STATUS.md` splits working, mock, broken, and missing. |
| Document incomplete components, mock data, dead routes, and failing integrations | done | inventory | Same file. Includes the 404 on `/api/v1/conversations/flags`, the unused Phaser mount on the live page, and the two failing registry tests. |
| Protected implementation branch and baseline test report | partial | inventory | This commit is on `feature/phase-0-reconnaissance`, not on `main`. The baseline report is written. The live sky view is still uncommitted on the other worktree, so this commit does not protect those bytes. |
| `docs/MASTER_BUILD_PLAN.md` and `docs/IMPLEMENTATION_STATUS.md` | done | inventory | Both files exist and use `not-started` / `partial` / `done`. |
| Acceptance criteria and dependencies for every feature | done | the task list | Each row in this file has both. |
| Verify development, staging, and production separation | done | inventory | Only local exists. Staging and production are absent. Non-local boot is refused. That is separation by refusal, not three deployed environments. |
| GitHub Actions lint, typecheck, tests, and build | partial | none | `.github/workflows/ci.yml` already has those jobs. It was not run on this commit. Actions are not pinned to SHAs. |

Phase 0 gate: not closed. `scripts/check.sh` exits 1. See the baseline report.

## Phase 1 — Core infrastructure and backend

Goal: shared contracts, auth that is real, and a local stack that matches the running database. Do not rewrite the FastAPI app to get there.

| Task | Status | Depends on | Acceptance |
| --- | --- | --- | --- |
| TypeScript frontend and FastAPI without an unnecessary rewrite | partial | Phase 0 | `apps/web` and `services/api` already run. A later change keeps those processes and the paper boot rules. |
| Shared schemas for agents, floors, tasks, messages, alerts, orders, and audit events | partial | none | Pydantic models and `apps/web/src/api/types.ts` cover agents, messages, and audit shapes. Floors, alerts, and an order command schema do not exist. An order schema must not add an order route. |
| Supabase migrations and development seed data | not-started | owner: organisation, region, cost | No Veytrix Supabase project. Alembic on local Postgres is the migration tool. Do not reuse nexgrail, gridlock, or avyro. |
| Authentication, RBAC, and row-level security | not-started | Supabase or another auth design you approve | Diagnostics say `auth` `not_configured`. RLS policies from migration `0009` are not an API control while the login can bypass them. Do not document RBAC as present. |
| Organisation, user, member, and agent identities | partial | auth | Ten agent rows exist. There is no organisation, user, or member table. |
| Redis or an equivalent durable job queue | not-started | a host decision | No `REDIS_URL`. No worker process. |
| API health, structured logs, and error reporting | partial | none | `/health`, `/ready`, and JSON request logs exist. There is no error reporter and no paging. |
| Secrets management and server-only credentials | partial | none | Settings read the environment. No secrets manager. No `.env` is committed. `VITE_` must not carry a secret. |
| Docker development environment and service startup | partial | none | `docker-compose.yml` builds Postgres, API, and web on loopback. The running database is a container on port 5433, not the compose file's port 5432. |
| Rate limits, idempotency keys, and retry / dead-letter handling | partial | a queue if retries are durable | Rate limit is process-local. Some ledger writes use idempotency keys. There is no dead-letter queue. |

Phase 1 gate: not met. Auth is the blocker for anything that is not loopback.

## Phase 2 — F1 sky view and navigation

Goal: one atrium you can move through. React Three Fiber and Three.js are the target renderer. They are not installed. The current sky view is HTML and CSS in the preview worktree.

| Task | Status | Depends on | Acceptance |
| --- | --- | --- | --- |
| Final F1 atrium and panoramic sky view | partial | do not discard the preview | `SkyFloor.tsx` is one HTML/CSS room. It is not a final panorama and not 3D. |
| Interactive 3D headquarters with React Three Fiber and Three.js | not-started | a decision to add those dependencies | Neither package is in `apps/web/package.json`. Phaser is installed and is not the mounted live page. |
| Orbit, pan, zoom, focus, and camera reset | partial | the current sky view | The HTML floor has a shot scale and offset. It is not an orbit camera. |
| Floor selection and building cutaway | not-started | a building model | One floor. No cutaway. |
| Elevator with current-floor indicator | not-started | more than one floor | No elevator. |
| Click a floor to enter, and return to the sky view | partial | the current page | Desks open a dialog. There is no other floor to enter. |
| Real-time presence, status, and tooltips | partial | Phase 5 for true realtime | The page polls. Supabase Realtime is `not_configured`. Desk status on the live API is `enabled` for paper research. |
| Activity ticker, market overview, portfolio status, and alerts panel | partial | market routes | Live Activity Feed exists and scrolls in CSS. It is not a market or portfolio tape, and there is no alert inbox. |
| Loading, empty, disconnected, and error states | partial | none | Failed reads are not replaced with invented prices. A full matrix of those four states was not tested in the browser this pass. |
| Mobile and tablet performance, and an accessible 2D fallback | partial | a browser pass | The current view is already 2D. Chat CSS collapses to a bottom sheet under 760px. No tablet pass was run. Reduced motion turns the bubble animation off. |
| Persist camera and floor preferences | not-started | a floor switch | Nothing is stored for the camera. |
| Visual regression, interaction, and performance tests | partial | the preview tests | `SkyFloor.test.tsx` covers table walking. No screenshot suite and no frame-time budget. Those preview tests were not executed in this pass. |

Preserve while changing this phase: scrollable Live Activity Feed, `.thought.live.overlay` speech bubbles, Roads and Dayvid off the table, Dayvid walking, boardroom table, north-wall VEYTRIX SANCTUM sign, chat composer, registry `enabled` with trading flags false.

Phase 2 gate: not met. The live page is a 2D room, not the 3D headquarters.

## Phase 3 — Claude agent runtime

Goal: a server-side model adapter whose output cannot trade. Cursor is for writing code, not for production inference. There is no Anthropic adapter and no model key. Do not invent `model_generated` text.

| Task | Status | Depends on | Acceptance |
| --- | --- | --- | --- |
| Server-side Anthropic Claude adapter | not-started | owner: provider account and model ids | No adapter module. `ANTHROPIC_API_KEY` unset. `GET /api/v1/inference/posture` says paid inference is off. |
| Model configuration and per-agent model selection | not-started | the adapter | `model_router.py` refuses paid providers. It does not select a Claude model. |
| Identities for Roads, Dayvid, Nyx, Astra, Lyra, Vex, Cipher, Aegis, Midas, and YIELD | partial | a written pairing | Preview names exist for nine desks. YIELD does not. `FUTURES-01` is Futures. The Phase 0 roster doc still leaves Astra and Dayvid unassigned. |
| Role prompts and capability boundaries | not-started | identities | No system prompts. Boundaries today are registry flags and a deny list, not prompts. |
| Agent registry, lifecycle, and heartbeats | partial | none | Registry rows and `enabled` / `paused` / `disabled` exist on the live database. Nothing writes a heartbeat. |
| Persistent tasks, conversations, and run history | partial | Phase 0 comms, which already shipped on the other branch | Conversations and messages exist in the preview API. Tasks and `agent_runs` are not a worker history. |
| Approved tool registry with JSON Schema checks | partial | none | `POST /api/v1/supervisor/tools/check` denies unknown and dangerous names. It does not run a tool. |
| Scoped memory with Postgres or pgvector | not-started | a reason to store embeddings | pgvector is not installed. Chat rows are not a memory index. |
| Bounded debates and structured handoffs | partial | the comms store | Preview discussions and boardroom sessions exist, with scripted replies. They are not model debates. |
| Roads delegation, priority, and approval routing | not-started | a runtime | Roads is a desk and a walker. Roads cannot grant a permission, move money, or bypass risk. |
| Scheduled, event-driven, and user-triggered runs | partial | a model, for model runs | The user can send a chat message. Nothing schedules a model call. MAC-01's clock cannot be started from the API. |
| Token budgets, spend caps, concurrency, and timeouts | partial | a provider bill | Inference posture has a ceiling of 0 and spend of 0. There is no token meter. |
| Error recovery, retries, and manual intervention | not-started | a worker | No agent worker. |
| Provider failure fallback that still cannot raise permissions | not-started | the adapter | There is no provider to fall back from. A fallback must not set `can_submit_orders`. |
| Evaluation tests for tools, hallucinations, and unsafe actions | partial | none | Comms tests reject `model_generated` in this build and keep `live_execution` false. There is no hallucination suite because there is no model. |

Phase 3 gate: not met. Blocked on a model account. Do not fake replies to look like Claude.

## Phase 4 — Floors F2–F9 and B1

Goal: the rest of the building, each room honest about its data. Not started as rooms. Some underlying desks exist on the one sky-view floor.

| Task | Status | Depends on | Acceptance |
| --- | --- | --- | --- |
| F2 engineering workstations, repository status, CI, and deploy panels | not-started | Phase 2 floor switch | No F2 scene. GitHub is not shown in the UI. |
| F2 GitHub commits, pull requests, checks, and engineering tasks | not-started | a GitHub identity you approve | No GitHub client in the app. |
| F3 Cipher laboratory and experiment dashboards | not-started | Phase 6 | Cipher is a desk on F1, not a lab. |
| F3 3D globe with licensed geospatial layers | not-started | a licence | A local worldview page exists on the preview branch. It is not a licensed 3D globe and it sends no order. |
| F4 Midas treasury vault, ledgers, allocation, payout preparation | partial | Phase 8 | Treasury page shows a projection. No vault scene and no payout button. |
| F5 Aegis risk centre, limits, exposure, and kill switch | partial | Phase 7 | Risk page and MAC-01 kill-switch engage exist. Aegis is not a separate deterministic gateway in front of a broker. The kill switch is a flag, not a floor. |
| F6 five trading desks and strategy / position dashboards | partial | Phase 7 | Desk rows and a Strategy page exist. They are not five floor scenes. |
| F6 sessions, orders, signals, and paper / live status | partial | a paper connection for live numbers | Signals and orders routes read the local MAC-01 ledger. Live status stays impossible. Paper broker numbers are absent. |
| F7 YIELD investments and dividend analytics | not-started | a decision that YIELD is a new desk | No YIELD code. Do not rename `FUTURES-01` in passing. |
| F8 AI Ops directory, task queue, and permission requests | partial | Phase 3 | Agency page lists desks. There is no task queue and no permission grant. |
| F9 founder office, Roads station, boardroom, and meeting history | partial | the preview boardroom | The sky view has a boardroom table and a gather animation in comms. It is not F9, and it does not book a meeting. |
| F9 Wednesday meetings and a potluck scoreboard | partial | a confirmed time | Reminder dates exist. Meeting time is `unconfirmed`. No scoreboard. |
| B1 server, database, worker, API, and infrastructure health | partial | workers, which do not exist | System page reads local posture and feed health. No worker and no infrastructure map. |
| A visual identity and an avatar per floor | partial | the floors | The sky view has per-desk colours. Other floors do not exist. |
| Navigation, breadcrumbs, and elevator transitions | not-started | Phase 2 elevator | The shell has routes. Sanctum has no breadcrumb floor stack. |
| Replace production-facing mock panels with data or an honest empty state | partial | each integration | SAMPLE and scripted speech are labelled in code. A pass across every panel was not done in the browser. |
| Floor access control and member visibility | not-started | Phase 9 | No member role. Every local page is open. |
| Desktop, tablet, and mobile tests for every floor | not-started | the floors | No floor to test. |

Phase 4 gate: not met.

## Phase 5 — Real-time communication and alerts

Goal: presence and alerts that survive a refresh. Today the browser polls. Supabase Realtime is not provisioned.

| Task | Status | Depends on | Acceptance |
| --- | --- | --- | --- |
| Supabase Realtime presence and message channels | not-started | Phase 1 Supabase project | Live flags: `realtime` `not_configured`. A doorbell client exists in the preview and does not connect without a project. |
| Founder-to-agent and agent-to-agent chat | partial | the preview comms API | Chat composer and stored messages exist on the preview branch. Replies are not a model. This pass did not send a message. |
| Threads, transcripts, and search | partial | stored messages | Threads exist. Search across history was not found as a product feature. |
| Voice-ready metadata and speaking avatars | partial | none | `voice_chat` is false. Bubbles show speech text. No audio. |
| Event bus for agent, research, risk, treasury, and infrastructure events | not-started | Phase 1 queue | `events.py` has shapes. They are not published. |
| In-app notification centre with unread and acknowledgement | not-started | the bus | No notification inbox. |
| Browser push and optional mobile push | not-started | auth and a push provider | No push subscription. |
| Severity, deduplication, and escalation | not-started | the inbox | Absent. |
| Critical risk alerts and an emergency halt notification | partial | the kill switch | MAC-01 kill switch can be engaged from the API. It does not page anyone, and it is not a global halt of a broker session. |
| Daily executive summary and Wednesday preparation | not-started | Phase 3 and a calendar | No summary job. |
| Scheduled briefing delivery and notification preferences | not-started | a scheduler you can start | No preference store. |
| Tests for delivery, retries, offline recovery, and permissions | not-started | the channel | Preview tests cover a Realtime payload shape with a fake transport. They do not prove delivery. |

Phase 5 gate: not met. Polling remains the path.

## Phase 6 — Market intelligence and research

Goal: sourced data and a research record. Display quotes are not a research platform.

| Task | Status | Depends on | Acceptance |
| --- | --- | --- | --- |
| Market-data adapters and source provenance | partial | none | SAMPLE is in-process. Coinbase public candles and tickers are a display. Provenance is a label, not a lineage store. |
| OHLCV ingest, validation, normalisation, and storage | partial | a store decision | Bars are fetched to draw. They are not a warehouse. Price rows are not seeded into Postgres by the API. |
| Stock, ETF, crypto, and market research pipelines | not-started | ingest | Desk names exist. Pipelines do not. |
| TradingView-compatible signal intake where you authorise it | not-started | a webhook secret and a written yes | Lightweight Charts draws API bars. No TradingView alert webhook. |
| Quiver Quant and other licensed adapters | not-started | credentials and a licence | No client. |
| Historical sets, freshness checks, and missing-data alerts | partial | Coinbase health | `GET /api/v1/market/health` marks a feed stale or down and does not invent a price. No historical archive. |
| Indicator library including EMA 20 and EMA 50 | not-started | a library, separate from the order path | MAC-01 computes SMA 20/50 inside the CLI. There is no shared EMA module. |
| Cipher backtest and experiment runner | not-started | stored bars | A MAC-01 fixture backtest exists and is labelled hypothetical. It is not Cipher's runner. |
| Autoresearch-style keep-or-revert experiments | not-started | the runner | Absent. |
| Provenance, citations, and reproducible artefacts | partial | none | Research notes and source events are local rows. No citation graph. |
| Research debates with an independent Aegis review | not-started | Phase 3 | Aegis cannot yet review a model debate. Risk previews are deterministic and do not read a debate. |
| Publish results to F3, F6, and an executive view | not-started | those floors | No such publish path. |

Phase 6 gate: not met.

## Phase 7 — Paper trading and risk engine

Goal: Alpaca **paper**, MAC-01, and a deterministic risk check that can say no. Live execution stays disabled until a separate approval. The signal in code is SMA 20/50, long only, not EMA.

| Task | Status | Depends on | Acceptance |
| --- | --- | --- | --- |
| Alpaca paper connectivity and credential isolation | partial | regenerated paper keys, not pasted into chat | Adapter exists in the CLI only. Paper key variables were unset. The API does not read them. |
| MAC-01 20/50 EMA long-only strategy | partial | a written change if you want EMA | The built rule is SMA 20/50, long only, AAPL. EMA is not implemented. Do not relabel SMA as EMA. |
| Backtest with fees, slippage, and a market calendar | partial | calendar data | Fixture backtest is hypothetical. `calendar` on the schedule route stays `not_read`. |
| No look-ahead, no leakage, no invalid historical signals | partial | the backtest | The crossover uses completed closes in the unit tests. A leakage audit of a stored series was not run. |
| Deterministic position sizing and risk checks | partial | none | `services/risk` uses `Decimal`. `POST /api/v1/risk/size` returns a share count with `execution_permitted` and `order_submitted` false. |
| Independent Aegis approval or rejection | partial | a broker path, which must stay closed until you approve one paper submit | Shield preview can fail a check. It cannot approve an order. Model output cannot call it into a submit. |
| Per-trade, daily-loss, drawdown, and exposure limits | partial | none | CLI caps: $100 notional, $100 position, 2 orders a day, one open order. Daily and weekly stops are stored and not enforced on a ledger. Drawdown is not a live control. |
| Order state machine, idempotent submit, and reconciliation | partial | a paper submit you authorise | CLI has a client id and a no-retry lookup. API reconciliation never marks a row broker-confirmed. |
| Paper execution, fills, cancels, and errors | not-started | paper keys and written approval for one submit | No paper order has been sent. |
| Trade journal, attribution, and performance | partial | fills | Strategy page reads local fills. There are no broker fills to attribute. |
| Emergency stop, stale-data stop, and broker-disconnect handling | partial | a connected session | Kill switch engage exists. Quote age is checked in the preview policy. Nothing is connected to disconnect. |
| Tests for gaps, partial fills, and duplicate events | partial | none | Unit tests cover caps, shorts, leverage, and a withheld pass. They are not a broker red-team. |
| Supervised paper trading and an evidence pack | not-started | the one authorised submit | Clock has not started. |
| Live execution disabled until a separate approval | done | none | This is the current state, and it is the one that must stay. `live_submission_possible` false. Do not "finish" this row by turning live on. |

Phase 7 gate: not met. The `done` row is a prohibition, not a paper go-live.

## Phase 8 — Treasury and portfolio

Goal: a ledger and a 50/50 policy with a $2,000 cap. No transfer in this plan until you approve a real payout path.

| Task | Status | Depends on | Acceptance |
| --- | --- | --- | --- |
| Double-entry ledger and reconciliation jobs | not-started | Phase 7 fills | No double-entry journal. |
| Separate deposits, withdrawals, realised P&L, and unrealised P&L | partial | fills | MAC-01 performance maths exist for local fills. There are no deposits or withdrawals. |
| 50/50 eligible-profit policy with a $2,000 cap | partial | none | `project_month` splits caller-supplied figures and caps the payout figure at $2,000. It does not pay. |
| Monthly calculation on the 5th and an approval step | partial | a proposal row | Review date is the 5th, or the following Monday when the 5th is a weekend. No approve route. |
| No-profit, loss, and rollover behaviour | partial | the projection | Tests cover a negative month and carryforward. They do not move cash. |
| YIELD dividend tracking and a reinvestment policy | not-started | YIELD, which does not exist | Absent. |
| Exposure, allocation, and performance dashboards | partial | a broker balance | Portfolio page is paper positions you typed. It is not a broker allocation. |
| Accounting export, tax data, and audit records | not-started | the ledger | Size audit rows exist. They are not a tax export. |
| Your authorisation before any external movement | done | none | Same meaning as the Phase 7 live row: the prohibition holds. No bank client exists. |
| Tests for payout maths and ledger consistency | partial | a ledger | Projection tests exist. Ledger consistency tests do not, because the ledger does not. |

Phase 8 gate: not met. The $2,000 figure is a projection cap, not a payment.

## Phase 9 — Member portal and executive controls

Goal: invitation-only access. Not started. Auth is not implemented, so this phase cannot be described as present.

| Task | Status | Depends on | Acceptance |
| --- | --- | --- | --- |
| Invitation-only onboarding | not-started | Phase 1 auth | No invite table. |
| Founder super-admin and scoped member roles | not-started | auth | No roles. |
| Read-only member sky view, floors, and activity | not-started | Phases 2 and 4 | No member session. |
| Portfolio and potluck scoreboard visibility | not-started | Phase 8 and a scoreboard | No scoreboard. |
| Daniel engineering view with GitHub activity | not-started | F2 GitHub | No Daniel identity in the repo. |
| Future COO role, inactive until assigned | not-started | roles | No COO row. |
| Roads permission requests that cannot self-grant | not-started | Phase 3 | Roads has no grant tool. Keep it that way until a request can only be approved by you. |
| Access review, session revocation, and audit | not-started | sessions | No sessions to revoke. |
| Privacy and unauthorised-access tests | not-started | a second role | Cannot test a role that does not exist. |

Phase 9 gate: not met.

## Phase 10 — Deployment, reliability, and release

Goal: a paper deployment you can restore. Live trading stays the separate checklist in `docs/RELEASE_CHECKLIST.md`. No deploy in this pass.

| Task | Status | Depends on | Acceptance |
| --- | --- | --- | --- |
| Reproducible development, staging, and production builds | partial | Phase 1 | `scripts/check.sh` builds the web app. Only the development machine exists. Staging and production builds do not. |
| AWS for the API and the frontend | not-started | a budget you approve | You previously chose local-only. No AWS account is configured. `AWS_ACCESS_KEY_ID` unset. |
| Optional homelab with Docker and a private network | not-started | a machine that is not this laptop's loopback | Compose is local. It is not a homelab deploy. |
| Backups, restore drills, and migration rollback | not-started | a backup target | Not drilled. `0012` has a downgrade function and it was not run. Do not run it against the live database without a backup and an explicit yes. |
| HTTPS, network segmentation, and secret rotation | not-started | a host | Loopback HTTP only. |
| Uptime, queue depth, cost alerts, and central logs | not-started | a host and a queue | JSON logs stay on the laptop. |
| Graceful degradation when Claude or a market provider fails | partial | those providers | A down Coinbase feed does not invent a price. Claude cannot fail because it is not called. |
| Security scan, dependency audit, and a penetration-test list | partial | none | `scripts/scan_secrets.py` found nothing on 13 November. `npm audit` and `pip-audit` were not run this pass. No penetration test. |
| End-to-end tests across floors, agents, and paper trading | not-started | those features | No browser end-to-end runner is installed. |
| Runbooks, recovery, and founder controls | partial | none | READMEs describe local boot and the live gate. There is no on-call runbook. |
| Publish a paper-trading release and watch it | not-started | `docs/RELEASE_CHECKLIST.md` paper rows | Paper release is not ready. |
| Write the live-trading criteria as a separate approval | partial | none | `docs/RELEASE_CHECKLIST.md` has that section. The approval itself does not exist. |

Phase 10 gate: not met.

## What this pass will not mark done

- Any Phase 1–10 task above, including ones that are `partial` from earlier work.
- A paper order, a live order, a payout, a Supabase project, or a Claude call.
- The preview worktree's uncommitted sky-view edits. They stay where they are.
