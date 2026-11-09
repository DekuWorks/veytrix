# Agent communication: repository analysis

Spec: `VEYTRIX_AGENT_COMMUNICATION_CURSOR_TASKS.md` (read in full from `~/Downloads`; the repo has no copy, so there was nothing to diff). Date: 9 November 2026. Branch `feature/agent-communication`, cut from the sky-view state at `5ef96c6` plus the uncommitted 17:43 sky view (committed first as `f9b0824`). Author: Claude, in Cursor. This is a self-review, not an independent one.

## 1. The ten agents

Read from the code, not from the spec. The spec says "all 10 existing agents" and does not name them.

| Code | Sky-view name | Role label | Desk slug | Registry id | Defined in |
| --- | --- | --- | --- | --- | --- |
| `SUPERVISOR-01` | Roads | AI Commander | `supervision` | `a1000001-…-000000000001` | `SanctumPage.tsx` `ROSTER`, `SkyFloor.tsx` `CREW`, migration `0009` |
| `DAY-01` | Dayvid | Day desk | `equities-session` | `a1000002-…` | same |
| `STOCK-01` | Vex | Stock desk | `equities-swing` | `a1000003-…` | same |
| `CRYPTO-01` | Nyx | Crypto desk | `crypto-display` | `a1000004-…` | same |
| `DEFI-01` | Cipher | DeFi desk | `simulated-swap` | `a1000005-…` | same |
| `ETF-01` | Lyra | ETF desk | `etf` | `a1000006-…` | same |
| `RESEARCH-01` | Astra | Research desk | `research` | `a1000007-…` | same |
| `RISK-01` | Aegis | Risk desk | `risk` | `a1000008-…` | same |
| `TREASURY-01` | Midas | Treasury desk | `treasury` | `a1000009-…` | same |
| `FUTURES-01` | Futures | Futures desk | `futures-research` | `a100000a-…` | `SanctumPage.tsx`, `SkyFloor.tsx`, migration `0010` |

Layers that define or consume the list:

- Database: `private.agents` (migrations `0009`, `0010`). The registry `display_name` is generic ("Risk desk"). The persona names live only in code.
- API: `model_router.PERSONAS` has nine names and no `FUTURES-01` (an existing test pins that). `comms/roster.py` is new and has all ten.
- Web: `apps/web/src/api/types.ts` `AGENT_CODES`, `SanctumPage.tsx` `ROSTER`, `SkyFloor.tsx` `CREW` and `DESKS`.

`tests/test_comms_roster.py` fails if the new roster, the migrations, `PERSONAS`, `ROSTER`, or `CREW` drift.

**Open item for the owner.** `docs/phase-0/agent-roster.md` on `feature/phase-0-reconnaissance` records that Astra and Dayvid are existing desks whose codes were *not assigned*, and its inventory test fails if a roster row uses either name. The sky view already pairs them: Astra is `RESEARCH-01` and Dayvid is `DAY-01`. This branch follows the code. If the owner has not confirmed the pairing, that Phase 0 test and doc will disagree with this branch at merge.

## 2. What conversation code existed

| Piece | Where | Real or scripted |
| --- | --- | --- |
| Avatar speech bubble | `SkyFloor.tsx` `showLine` → `SanctumPage.tsx` `speak()` | **Scripted.** `POST /api/v1/inference/route` with a task picked by `code.charCodeAt(0) % 5`. The text is the router's `reason` ("deterministic") plus "No order is sent." |
| Who speaks | `SkyFloor.tsx` proximity effect | **Scripted.** Two avatars within 7% of each other triggered a bubble. |
| Desk quick buttons (Size, Crossover, Split…) | `SanctumPage.tsx` `askDesk` | **Scripted.** Same route, same text. |
| `AgentDock` composer | `sanctum/ui/AgentDock.tsx` (21st.dev Agent Dock, adapted) | Posted to `askDesk`. It had no reply thread. |
| Activity feed | `SanctumPage.tsx` `FEED` | **Scripted and untrue.** "Scanning intraday setups", "Reviewing Topstep rules" while every desk is disabled and nothing runs. |
| Model router | `model_router.py`, `routers/inference.py` | Routing posture only. No provider is called. `paid_inference_enabled` is false, no Ollama URL. |
| Supervisor tool gate | `routers/supervisor.py`, `tool_gate.py` | Checks a tool name. Runs nothing. "Chat is not configured." |
| Movement and wander | `SkyFloor.tsx` | Scripted walking between the centre, the boardroom, and home. Not speech. Kept. |
| Boardroom | `SkyFloor.tsx`, `SanctumPage.tsx` | A camera preset and a static note. Nobody meets. |

No message table, no conversation route, no agent-to-agent path, no group chat existed.

## 3. What Supabase Realtime did

- `apps/web/src/sanctum/realtime.ts` had `openSanctumChannel`, a browser-only subscriber to broadcast event `desk` on channel `sanctum-status`, gated on `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`, and refusing a service-role key.
- The sky view never called it. Nothing on the server published to it. No Supabase project is provisioned. The database is local Postgres (`127.0.0.1:5433`), schema `private` for the registry.
- Other Supabase containers on this machine (`nexgrail`, `gridlock`, `avyro`) belong to other projects. They were not used.

## 4. Runtime facts that shaped the design

- No language model is configured (`paid_inference_enabled` false, no Ollama). Cursor's subscription does not run agents (`docs/cursor-subscription.md`).
- No desk runs a worker. `agent_runs` is empty. A truthful answer to "what are you working on?" is "nothing is running", plus what the desk can read.
- The running API (port 8000) was started from the main repo at 14:38 with the sky-view code loaded in memory (it answers `/api/v1/inference/route`). The main repo's working tree is now the Phase 0 branch and has no inference router. The preview worktree is the only checkout that has both the sky view and this work.
- There is no auth. CORS allows `127.0.0.1:5173` and `localhost:5173` only.

## 5. Gaps against the spec

| Spec phase | State before | State after this branch |
| --- | --- | --- |
| 0 Audit, contracts, flags, acceptance, rollback | none | This document, five feature flags (`live_execution` is a constant false), tests, rollback in `docs/agent-communication/README.md`. |
| 1 Messaging foundation | none | Typed envelope, six `private` tables with RLS, append-only messages and events, validation, per-process rate limit, Realtime doorbell after commit. **Not done:** authentication (none exists), retention policy, encrypted secret handling beyond a server-side key held in an env var. |
| 2 Direct chat, all ten | none | Done for all ten, persisted, resumable, searchable, pin and archive, clarifying questions, the five spec commands, glossary at three levels. **Not done:** token streaming (replies are instant, so the UI shows a typing state only), cancel. |
| 3 Agent-to-agent | none | Bounded rule-based discussions with round, message, and loop limits, independent-source rule, explicit dissent, Supervisor moderation, an autonomous trigger behind a flag that is off. **Not done:** a language model, so turns are `simulated`; no scheduler calls the trigger. |
| 4 Groups and boardroom | none | All-desks room, custom groups, @mentions, threads, unread counts, pause, resume, redirect, close, boardroom sessions with agenda, minutes, tallies, proposed tasks. **Not done:** votes beyond an evidence tally, topic rooms, notifications, DayPilot (Dayvid has no calendar access). |
| 5 Sanctum visualisation | scripted bubbles | Bubbles are stored messages with origin tags; desks gather in the boardroom for discussions; Conversation Monitor; Follow mode; replay with controls; bottom-sheet layout below 760 px; keyboard, live region, reduced motion, forced colours. **Not done:** command palette, activity timeline component, decision inspector. |
| 6 Tool-aware truth | one canned line | Status vocabulary (`ToolStatus`), `status_for_order` (`filled` needs a broker order id and a filled quantity), "what actions were executed" reads the ledger, the canned line is gone. **Not done:** events for every research query, awaiting-approval flow (no approval path exists, by design). |
| 7 Activity feed, audit | none | `message_events` is an append-only lifecycle log with correlation ids; the feed shows stored messages. **Not done:** transactional outbox, decision inspector, audit export, policy and model versions. |
| 8 Research feedback | none | **Not done.** |
| 9 Model gateway, costs | router posture only | **Not done.** Origin `model_generated` exists in the schema and is never written. |
| 10 Trading integration | MAC-01 exists | **Untouched by design.** Chat cannot reach it. |
| 11 Voice, WhatsApp | none | **Not done.** `voice_chat` flag exists and is off. |
| 12 Tests, deployment | n/a | 440 pytest and 275 vitest pass. **Not done:** E2E in a browser run in CI, GitHub Actions changes, metrics. |

## 6. Feature flags

`agent_chat` (on), `group_chat` (on), `autonomous_discussions` (off), `voice_chat` (off), `live_execution` (constant false; not read from any setting or environment variable; `GET /api/v1/comms/flags` always reports false). Environment variables: `VEYTRIX_FLAG_AGENT_CHAT`, `VEYTRIX_FLAG_GROUP_CHAT`, `VEYTRIX_FLAG_AUTONOMOUS_DISCUSSIONS`, `VEYTRIX_FLAG_VOICE_CHAT`.

## 7. Acceptance tests and rollback

Acceptance is the test list in `docs/reviews/agent-comms-completion.md`. Rollback: `alembic downgrade 0010_futures_desk` drops the six tables and nothing else; reverting the branch restores the scripted bubbles; the flags can switch chat off without a deploy.
