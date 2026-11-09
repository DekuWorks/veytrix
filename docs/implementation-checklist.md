# Implementation checklist

Source: `VEYTRIX_CURSOR_CODEX_MASTER_BUILD.md` version 4.1 (November 2026). Audit date: 8 November 2026. Branch: `feature/sprint-0-foundation` (no commits, no remote). Status tags were set by reading the tree and by the live checks in `docs/architecture/current-state.md`.

Tags: **BUILT** means the behaviour is in the tree and, where it is an external integration, it was checked this pass. **PARTIAL** means some of it exists. **NOT STARTED** means it is absent. **BLOCKED** means it needs credentials, paid provisioning, or an explicit financial authorisation from the owner. A blocked item is not a licence to build around it.

Codex was not run. The `codex` command is not on `PATH`. Do not treat this file as an independent security review. `docs/reviews/PENDING.md` still stands.

Phase 01’s cloud items are still blocked. A local schema slice of that phase was applied on 8 November 2026 (migration `0009_agent_registry`). A later local slice of Phase 02 added a read-only registry route, a size-request audit row, event shapes with no publisher, and a read-only Agency page. A further local slice added `GET /api/v1/audit/log` and a desk page that cannot enable trading. Phases that need keys, a paid account, or a transfer are still blocked.

## Owner decisions where the plan conflicts

1. Order size is `$100` notional and a `$100` position, not one share (Phase 05). See ADR 0002.
2. The live gate stays in the MAC-01 CLI and stays unused. No live order is authorised (Phase 13).
3. Swaps are simulated and never signed. Networks are Solana devnet, Ethereum Sepolia (`11155111`), and Base Sepolia (`84532`). Mainnet RPC is not adopted (Phase 07).
4. The app stays on this machine. No AWS (Phase 12, and step 7 of the plan's "do this now" list). No Veytrix Supabase project until organisation, region, and cost are approved (Phase 01). Do not reuse the `nexgrail` or `gridlock` stacks.
5. The obsidian and jade shell stays. The 21st.dev Dashboard Shell is not copied (Phase 08).

## Blocked on the owner

These stop the named phase. Safe local work that does not need them can continue. The registry pass did the local slice of Phase 01 and left the rows below blocked.

| Block | What you need to do | Phases |
| --- | --- | --- |
| Alpaca keys | Regenerate the paper key and the live key. The pair pasted in chat is compromised. Do not paste the new keys into chat. There is no `.env` in this tree. | 03, 05, 13 |
| First paper order | Say, in writing, that one Alpaca **paper** submit is authorised. None has been sent. | 03, 05 |
| Live trading | A separate authorisation. The eight-condition gate is not approval to use it. | 13 |
| Supabase | Name the organisation and region, and approve the quoted cost. No Veytrix project exists. | 01 |
| AWS | A new decision. You already chose local-only. Any ECS, SQS, NAT, or Secrets Manager spend needs a budget first. | 02 (SQS and Secrets Manager), 12 |
| DayPilot | Confirm the Wednesday meeting time (the plan leaves it TBD) and approve access. `daypilot-db` on this machine is not a Veytrix integration. | 10 |
| Apple distribution | An Apple developer account and a distribution path. The private App Store exemption is not assumed. | 09 gate |
| Model provider | Confirm which model API you will pay for, and the model ids that account can call. None is configured. | 06 |
| Bank payouts | A separate authorisation, plus the legal, tax, and benefits review the plan names. A `$2,000` software cap is not that review. | 11, 13 |

## Phase 00 — Audit and delivery discipline

- [x] Inventory web, API, dependencies, Coinbase, env, auth, DB, jobs, brokers, tests, and AWS. — **BUILT** — Written up in `docs/architecture/current-state.md` from the tree and from processes that were already up.
- [x] Baseline screenshots, working endpoints, issues, and constraints. Preserve live quotes and the theme. — **BUILT** — `docs/architecture/baseline/`; Coinbase tickers returned HTTP 200; theme unchanged. Full `scripts/check.sh` was not re-run.
- [x] `docs/architecture/current-state.md`, `docs/architecture/target-state.md`, and ADRs. — **BUILT** — ADR 0001 stands for API boot. ADR 0002 records the overrides above.
- [x] Branch strategy, CODEOWNERS, lint, types, tests, secret scan, dependency scan, CI, PR template, acceptance template. — **PARTIAL** — Branch note, CI workflow, ruff, pytest, Vitest, `scan_secrets.py`, pip-audit, npm audit, and `.github/dependabot.yml` are in the tree. PR template and acceptance template exist. CODEOWNERS has no GitHub login because this clone has no remote. Actions are not pinned to SHAs. GitHub CI has never run here. Dependabot does nothing until this repo has a GitHub remote.
- [x] Dependency-ordered issue board with owner, status, dependencies, complexity, and verification. — **BUILT** — `docs/issue-board.md` is a local board. No GitHub issues were opened.

**Gate:** not closed. The running app served Coinbase quotes and the secret scan is recorded below. CI has not passed on a commit, because there is no commit. Codex has not reviewed.

## Phase 01 — Supabase and a secure database

- [ ] Dedicated Veytrix Supabase project, with cost shown before provisioning. — **BLOCKED** — No Veytrix project. Other Supabase stacks on this machine must not be reused. Also conflicts with "stay local" until you reverse it.
- [ ] Supabase Postgres as the primary database, Supabase Auth, Realtime for UI, AWS for workers. — **BLOCKED** — Same hosting decision. Local Postgres on `127.0.0.1:5433` is the database in use.
- [ ] Versioned SQL and a local Supabase CLI, with separate dev and production projects. — **PARTIAL** — Alembic through `0009_agent_registry` is applied on `127.0.0.1:5433`. No Supabase CLI workflow.
- [ ] Non-exposed `private` schema and a narrow `public` schema. — **PARTIAL** — Schema `private` exists and is revoked from `PUBLIC`. New agency tables live there. `public.agent_registry` is a `security_invoker` view. Existing public tables were not moved, because the running API still queries them.
- [ ] Normalised tables listed in the plan (profiles through integration_health). — **PARTIAL** — Added `private.agents`, `private.agent_permissions`, and `private.agent_runs`. Treasury, meeting, profile, and conversation tables are still absent.
- [ ] Foreign keys, decimal money, idempotency keys, UTC timestamps, indexes, immutable financial rows. — **PARTIAL** — The new tables use foreign keys, UTC timestamps, and indexes. `agent_runs.idempotency_key` is unique. Audit, permission, and run rows reject update, delete, and truncate. The rest of the plan’s ledger is not built.
- [ ] RLS, owner-only, deny by default, no security-definer leaks. — **PARTIAL** — RLS is enabled and forced on the three private tables. A non-owner role sees no rows. The local `veytrix` role is a superuser with `BYPASSRLS`, so the API connection is not constrained. There is still no auth.
- [ ] Least-privilege DB roles, no service-role key in the frontend, pooled TLS connections. — **PARTIAL** — `PUBLIC` has no rights on schema `private`. No second login was created. The API still connects as the superuser role. No service-role key is in the web app.
- [ ] Supabase Auth MFA, JWT checks in FastAPI, login, logout, recovery, CORS allowlist. — **BLOCKED** — Needs the Supabase project. Today CORS is the local Vite origins only, and diagnostics reports `auth: not_configured`.
- [ ] Generated TypeScript types, Python models, migration CI, backup and restore test. — **PARTIAL** — SQLAlchemy models and Alembic exist. Backup restore has not been tested. Migration CI is "upgrade on local Postgres" inside the existing workflow, not a Supabase migration check.

**Gate:** not met. Organisation, region, cost, and auth are still required. Codex has not reviewed migration `0009`.

### Local subset completed this pass

These are done as local schema only. They do not close Phase 01.

- [x] Schema `private`, revoked from `PUBLIC`, with the agency tables in it and a `security_invoker` projection in `public`. — **BUILT** — Migration `0009_agent_registry`, applied on `127.0.0.1:5433`. Existing public tables were left in place.
- [x] Agent registry: nine desks, seeded `disabled`, with `can_submit_orders`, `can_sign`, `can_transfer_funds`, and `holds_credentials` forced false. Every permission row is `effect = 'deny'`. — **BUILT** — `test_agent_registry_migration_is_private_and_cannot_trade` and `test_alembic_upgrade_on_postgres_16`.
- [x] Append-only `audit_events`, plus append-only permission and run rows. — **BUILT** — The same Postgres test rejects update, delete, and truncate.
- [x] RLS forced on the three new tables, and a non-owner role sees nothing. — **BUILT** as a database test. — **Not** an auth design. Awaiting Codex review (`docs/reviews/PENDING.md` item 13).

Pros of doing this locally: the registry cannot grant an order, a signature, or a transfer, and the running API did not need a restart. Cons: a superuser connection bypasses RLS, treasury and meeting tables are still missing, and this is not Supabase. Confidence: high for the migration and the tests below. Medium for calling the row security “owner-only”, because the API role bypasses it.

## Phase 02 — Core backend, contracts, and observability

- [ ] FastAPI health, ready, `/api/v1`, OpenAPI, typed DTOs, validation, request ids, owner auth, rate limits, audit middleware. — **PARTIAL** — Health, ready, OpenAPI, validation, correlation ids, and a process-local rate limit exist. `POST /api/v1/risk/size` writes one `audit_events` row with that correlation id, and only when the size is stored. `GET /api/v1/audit/log` reads those rows and is GET only. A row that is not a safe size record, or that says an order was submitted, returns 503 and no row. Owner auth does not. There is still no audit row on every route.
- [ ] Event contracts (MarketBarClosed through DistributionProposed). — **PARTIAL** — The eleven shapes are in `services/api/veytrix_api/events.py`. They are not mounted, not queued, and not written to SQS. An order shape cannot say this API submitted it or that it was live. A distribution shape cannot say a transfer happened.
- [ ] Durable outbox to SQS, jittered retry, dead-letter queues, dedupe, tracing. — **BLOCKED** — SQS is AWS spend, and you chose no AWS.
- [ ] Pydantic Settings, a safe `.env.example`, AWS Secrets Manager, startup validation, redacted logs. — **PARTIAL** — Settings and startup refusal exist. Logs omit bodies and the database URL. There is no `.env.example` on purpose (placeholders are in the READMEs). Secrets Manager is blocked with AWS.
- [ ] JSON logs, metrics, traces, audit correlation, alerts, redaction. — **PARTIAL** — JSON logs and correlation ids exist. No metrics, traces, or alert routing.

**Gate:** not met. Authenticated API and durable publishing are absent.

## Phase 03 — Real Alpaca paper brokerage

- [ ] `alpaca-py` `TradingClient` with `paper=True` and paper-only credentials. — **PARTIAL** — The MAC-01 adapter can construct a paper client. No credentials exist. This pass did not call Alpaca.
- [ ] Adapter methods: account, clock, calendar, positions, orders, submit, get, cancel, updates, reconciliation. — **PARTIAL** — Submit, lookup by client id, positions, and open orders are in the MAC-01 runner. A general adapter with cancel and clock is not a shared service.
- [ ] Persist broker order ids and client order ids, including partial fills and rejections. — **PARTIAL** — The ledger has a `pending_submit` client id path. No broker id has been stored from Alpaca.
- [ ] Intent state machine, DB lock, broker idempotency, reconcile before retry, crash recovery. — **PARTIAL** — MAC-01 has an advisory lock and a no-retry lookup. It is not the plan's general intent machine.
- [ ] Manual paper smoke test after explicit owner authorisation, capturing the broker id. — **BLOCKED** — Needs regenerated keys and your authorisation. Do not mark this done from a unit test.
- [ ] UI shows broker-reported paper balance, buying power, positions, orders, reconciliation, clock. — **NOT STARTED** — The Strategy page reads the local ledger. Last run is "never". Empty P&L is not an Alpaca balance.
- [ ] Live credentials unreachable from the paper deployment. Fail startup if live mode is on unexpectedly. — **PARTIAL** — Separate env vars and the eight-condition gate exist. There is no separate paper deployment. The API refuses `VEYTRIX_ENABLE_LIVE_BROKER`.

**Gate:** not met. No genuine paper read and no broker-returned order id.

## Phase 04 — Independent Veytrix Shield

- [ ] Versioned policies: allowlists, budgets, buying power, sizing, daily order cap, concentration, stale data, spread, loss limits, no leverage or shorts. — **PARTIAL** — MAC-01 has $100 caps, 2 orders a day, long only, and a daily loss cutoff in config. The sizing route caps risk fraction at 0.02. There is no versioned Shield service. Sizing stops are stored and not enforced.
- [ ] Capital reservation and cross-agent locking, reconciled to broker buying power. — **NOT STARTED**
- [ ] Global pause and per-agent pause. Risk failure blocks new orders. Cancellation and liquidation policy defined without assuming stop-order prices. — **PARTIAL** — MAC-01 pause and kill switch, and the swap kill file, exist. They are not a global Shield.
- [ ] Owner approval for material policy or strategy-version changes, enforced on the server. — **NOT STARTED** — YAML edits are not an approval workflow.
- [ ] Tests for gaps, holidays, rejects, partial fills, outages, stale feeds, races, replays, and conflicting strategies. — **NOT STARTED** — MAC-01 unit tests exist. They are not this red-team set, and they were not re-run this pass.

**Gate:** not met.

## Phase 05 — MAC-01

- [ ] AAPL SMA 20/50 on at least 100 completed sessions. Research may use yfinance; live-capital decisions need licensed data. — **PARTIAL** — The runner asks Alpaca for 100 daily bars (`data_feed: iex` in config). No Alpaca call has been made. yfinance is not a dependency.
- [ ] Bullish and bearish crossover rules, with no repeated signal while still above or below. — **BUILT** — Rule and tests are in `services/quant`. Not verified against a live bar series from Alpaca.
- [ ] Long only, maximum one share, check holdings and open orders, next session under Shield. — **PARTIAL** — Long only, holdings check, and open-order check exist. Size is `$100` notional, which is the owner's rule, not one share. Shield as specified in Phase 04 does not exist.
- [ ] Store signal provenance, bar timestamps, strategy version, evaluation, broker execution, and P&L. — **PARTIAL** — Ledger tables and a Strategy page exist. No broker fill has been stored.
- [ ] Calendar-aware schedule, holidays, DST, restart catch-up, no duplicate candle evaluation. — **PARTIAL** — `schedule` uses the Alpaca calendar at 09:35 New York. It is not running. Catch-up after a restart is not demonstrated.
- [ ] Backtest with corporate actions, spread, slippage, and fees; benchmark; out-of-sample; paper-forward. — **PARTIAL** — A fixture backtest exists and is labelled hypothetical. It is not that study.
- [ ] Autonomous paper execution only after tests and an owner-approved activation policy. — **BLOCKED** — Needs the key regeneration and the paper-order authorisation. `submit_orders` is false.

**Gate:** not met. No autonomous paper order and no reconciliation against Alpaca.

## Phase 06 — AI supervisor and agency

- [ ] Persistent chat, streaming, history, agent registry, tool access, tasks, schedules, reports, incident notifications. — **NOT STARTED** — Research notes are local rows. No model is configured.
- [ ] Model-agnostic adapter. Verify real model ids. Do not hardcode an unverified "GPT Astra" id. — **BLOCKED** — Needs a provider account and a list of model ids that account can call.
- [ ] Roles SUPERVISOR-01, DAY-01, STOCK-01, CRYPTO-01, DEFI-01, ETF-01, RESEARCH-01, RISK-01, TREASURY-01. — **PARTIAL** — The nine names are readable from `GET /api/v1/agents`. `GET /api/v1/agency/desks/{code}` reads one desk, its notes, and the seven deny tools. There is no enable route. None of them runs, and none can trade.
- [ ] Supervisor has read-only account and research tools, never raw broker or bank credentials. — **NOT STARTED**
- [ ] Tool calls checked against schemas, allowlists, budgets, audit, timeouts, and prompt-injection defence. — **NOT STARTED**
- [ ] Morning and evening briefs, strategy status, incidents, trade explanations, weekly agenda, monthly accounting. — **NOT STARTED**

**Gate:** not met.

## Phase 07 — Trading departments

- [ ] DAY-01 US session, opening range, VWAP, liquidity filters, tested exits, day-trading rules. — **NOT STARTED**
- [ ] STOCK-01: MAC-01 plus a versioned swing universe. — **PARTIAL** — MAC-01 only. See Phase 05 for what is actually proven.
- [ ] ETF-01 screening, sector exposure, paper orders. — **NOT STARTED**
- [ ] CRYPTO-01 Coinbase ingestion with heartbeat, and a real paper crypto broker where the account allows it. — **PARTIAL** — Public Coinbase candles and tickers for BTC-USD, ETH-USD, and SOL-USD are a display. There is no ingestion worker and no crypto order path. The feed is not executable.
- [ ] DEFI-01 read-only mainnet and testnet RPC, public addresses only, simulated swaps with gas, slippage, impact, MEV, and liquidity. No signing. — **PARTIAL** — Simulated testnet CLI only, as you decided. Mainnet reads are not adopted. No wallet registry of public addresses beyond the simulated balances. Not signed off: the fill/order write was not re-run.
- [ ] RESEARCH-01 filings, macro, earnings, timestamped news, citations, point-in-time screens. — **PARTIAL** — Local note and source-event rows. No SEC client.
- [ ] Each agent has a state machine, telemetry, capital, kill switch, backtest, forward test, and acceptance report. — **NOT STARTED** — MAC-01 and the swap CLI have their own kill switches only.
- [ ] Options, futures, forex, commodities, and NFTs stay gated. — **BUILT** — They are absent, which is the correct state. Do not describe them as implemented.

**Gate:** not met. DeFi receipts are simulated in design; a fresh swap was not verified this pass.

## Phase 08 — Mission Control web

- [ ] Keep the dark obsidian and jade system. Improve with 21st.dev components where the licence allows. — **PARTIAL** — Theme is in place and was left alone. The 21st.dev shell stays rejected.
- [ ] Views listed in the plan (Overview through Settings). — **PARTIAL** — Overview, Agency, Market, Quant, Strategy, Events, Risk, Portfolio, Research, Audit, and Paper swaps exist. Agency lists disabled desks and opens one desk. That page cannot enable a desk or send an order. The Audit page reads the size journal and the size-audit log. Supervisor Chat, Paper Broker, Orders and Fills as broker views, Signals as their own page, Crypto, DeFi as labelled simulation beyond Paper swaps, Treasury, DayPilot, System Health, and Settings do not.
- [ ] TradingView Lightweight Charts, with the licence checked. — **BUILT** — `lightweight-charts` 5.2.1, Apache-2.0, attributed in the shell. Not the proprietary Charting Library.
- [ ] Separate broker balances, simulated portfolios, and demo figures. Show source, time, and stale-feed warnings. — **PARTIAL** — Labels exist on Coinbase, SAMPLE, paper positions, and simulated swaps. There is no broker-balance card.
- [ ] Emergency pause, per-agent enable, policy approval, and an explicit paper-order confirmation. — **PARTIAL** — Strategy page can pause, resume, and engage the MAC-01 kill switch. It cannot submit an order. No global pause and no policy-approval UI.
- [ ] Owner auth and server-side authorisation on every control. Accessibility and mobile checks. — **NOT STARTED** — No auth. Earlier UI tests cover the shell; they were not re-run, and this pass did not do a mobile pass.

**Gate:** not met. Financial cards are not all tied to a verified broker source, because no broker is connected.

## Phase 09 — Private iOS app

- [ ] React Native Expo app: Supabase Auth, secure storage, biometrics, push, chat, positions, alerts, Boardroom, emergency pause. — **NOT STARTED** — Also depends on the blocked Supabase decision.
- [ ] Private install via a real Apple distribution path. — **BLOCKED** — Needs your Apple developer account and a distribution method. A private App Store exemption is not assumed.
- [ ] Deep links, notification permission, token revocation, session expiry, offline and error states. — **NOT STARTED**

**Gate:** not met.

## Phase 10 — DayPilot Wednesday Boardroom

- [ ] DayPilot integration with scoped auth and a documented API. Missing endpoints only after you approve work in that other codebase. — **BLOCKED** — No access decision. `daypilot-db` listening on `0.0.0.0:5432` is not this integration.
- [ ] Recurring Wednesday meeting in America/New_York. Time is TBD until you confirm it. — **BLOCKED** — You have not confirmed a time.
- [ ] Supervisor agendas, reconciled P&L, drawdown, violations, trades, lessons, assignments. — **NOT STARTED** — Depends on Phase 06 and a real paper record.
- [ ] DayPilot calendar reminders; Veytrix stores minutes and action items. — **NOT STARTED**
- [ ] Webhook verification, event ids, retries, DST, idempotency, sync recovery. — **NOT STARTED**
- [ ] Reminders on the 1st (accounting close) and the 5th (payout review). — **NOT STARTED**

**Gate:** not met. No DayPilot event was created.

## Phase 11 — Treasury and monthly distributions

- [ ] Broker-reconciled realised P&L, costs, loss carryforward, periods, settled cash, reserves, and an audit trail. Separate deposits, realised, unrealised, and paper balances. — **NOT STARTED** — MAC-01 P&L is FIFO on local fills, before fees, and there are no fills.
- [ ] Payout policy: 50% of eligible positive net profit, maximum `$2,000` a month, review on the 5th, zero when eligible profit is not positive. — **NOT STARTED**
- [ ] Decimal formula and a transaction-safe monthly lock. — **NOT STARTED**
- [ ] Treasury prepares a proposal; you approve the transfer. Use a real broker ACH or wire, or a manual withdrawal if the broker has none. — **BLOCKED** — Needs a verified broker withdrawal path and your authorisation. Do not invent a bank transfer.
- [ ] Minimum bank-link metadata. No routing numbers in prompts, browser logs, or exposed tables. — **NOT STARTED** — Nothing is stored, which is the safe current state.
- [ ] Tests for double payout, failed transfers, weekends, negative months, carryforward, and settlement. — **NOT STARTED**
- [ ] Before live funding, a professional review of trust, SSI, Medicaid, tax, and account ownership. — **BLOCKED** — That review has not been commissioned. The software cap is not a benefits test.

**Gate:** not met. Paper-mode payouts are not even projections yet. No bank transfer exists.

## Phase 12 — AWS production

- [ ] IaC for ECS/Fargate, separate workers, SQS and dead-letter queues, EventBridge, Secrets Manager, IAM, CloudWatch, encrypted S3, network controls. — **BLOCKED** — You chose no AWS. Needs a new decision and a budget.
- [ ] Supabase remains the primary database. TLS, pooling, backoff, safe-stop, backup restore. — **BLOCKED** — Tied to Phase 01.
- [ ] GitHub Actions deploy, staging smoke, rollback, provenance. — **NOT STARTED** — CI lint and test jobs exist. Nothing deploys.
- [ ] Separate local, dev, paper-production, and live-production secrets. Paper cannot call live broker endpoints. — **PARTIAL** — Local only. MAC-01 paper and live keys are different env vars. There are no cloud environments.
- [ ] Single-active scheduling or locks, graceful shutdown, recovery, reconcile on boot, calendar and clock sync. — **PARTIAL** — MAC-01 takes a Postgres advisory lock. Nothing else in this list exists.
- [ ] Cost budgets and alerts. Measure AWS, Supabase, model, and data fees. — **BLOCKED** — No cloud spend is approved, so there is nothing to budget in an account.
- [ ] Load, chaos, outage, backup, penetration, and permission tests. Runbooks and on-call. — **NOT STARTED**

**Gate:** not met. Workers do not run without this laptop.

## Phase 13 — Performance and live-readiness

- [ ] At least 30 days of real Alpaca paper, then longer forward tests. No automatic promotion. — **BLOCKED** — Needs the paper-order authorisation and regenerated keys. The clock has not started.
- [ ] Net P&L, expectancy, profit factor, drawdown, exposure, turnover, costs, benchmark, order errors, reconciliation lag, uptime, risk compliance. — **NOT STARTED**
- [ ] Written go/no-go per strategy. No weekly profit target. — **NOT STARTED**
- [ ] Future live pilot: legal review, your approval, isolated credentials, about `$100`, one strategy, no leverage, shorts, or options. — **BLOCKED** — The `$100` cap matches the pilot size you already set. The authorisation and the review do not exist. The gate in code is not a yes.
- [ ] Live submission needs a separate deployment authorisation. — **BLOCKED** — Do not turn this on while finishing paper work.
- [ ] Live treasury transfers gated on broker capability, destination checks, your approval, compliance review, and the `$2,000` cap. — **BLOCKED** — Same as Phase 11.

**Gate:** not met. Paper production is not complete. Live production is not authorised. Profitability is not guaranteed.

## API examples in the plan

Not a phase. None of these are a finished, authenticated route. Do not add the ones that submit or approve money inside a later drive-by.

| Route | Status | Note |
| --- | --- | --- |
| `GET /api/v1/system/status` | **BUILT** as local posture | Database up or down, nine desks, `order_route: absent`. No broker balance. The process on port 8000 was not restarted, so that process does not serve this path yet. |
| `GET /api/v1/broker/paper/account` | **BLOCKED** | Needs regenerated paper keys. Must be broker-reported. |
| `GET /api/v1/broker/paper/orders` | **PARTIAL** | MAC-01 ledger orders are local, not a broker list. |
| `GET /api/v1/broker/paper/positions` | **PARTIAL** | Local paper positions are calculated sizes, not Alpaca positions. |
| `POST /api/v1/broker/paper/smoke-test/authorize` | **BLOCKED** | Needs your authorisation. The API must still not grow an unauthenticated order route. |
| `POST /api/v1/strategies/{id}/activate-paper` | **BLOCKED** | Same authorisation. CLI `submit_orders` is the only switch today, and it is false. |
| `POST /api/v1/strategies/{id}/pause` | **PARTIAL** | `POST /api/v1/strategies/mac-01/pause` exists. It is not generic and it is not authenticated. |
| `POST /api/v1/risk/emergency-stop` | **PARTIAL** | MAC-01 kill-switch engage exists. It does not cancel a resting Alpaca order. |
| `GET /api/v1/agents` | **BUILT** as a read | Nine disabled desks, trading rights denied, GET only. A row that could trade returns 503. No auth. Awaiting Codex. A live GET on PID 11188 returned 200 this pass. |
| `GET /api/v1/audit/log` | **BUILT** as a read | Size-audit rows only. GET only. An unsafe payload returns 503. PID 11188 returned 404. It was not restarted. |
| `GET /api/v1/agency/desks/{code}` | **BUILT** as a read | One desk and seven denies. No enable method. Same process gap: 404 on PID 11188. |
| `POST /api/v1/supervisor/chat` | **BLOCKED** | Needs a model provider. |
| `GET /api/v1/treasury/monthly-summary` | **NOT STARTED** | |
| `POST /api/v1/treasury/distributions/{id}/approve` | **BLOCKED** | Live transfer gate. Do not build it early. |
| `GET /api/v1/meetings` | **BLOCKED** | DayPilot time and access. |
| `GET /api/v1/market/health` | **PARTIAL** | Coinbase failures are surfaced per request. There is no market-health aggregate. |

## Verification, audit log and desk detail (8 November 2026)

- No new migration. A read of `alembic_version` on `127.0.0.1:5433` returned `0009_agent_registry`. Nine agents were `disabled` with `can_submit_orders` false. `audit_events` had 0 rows. No `.env` was created. No Alpaca call.
- The test client read `GET /api/v1/audit/log` and `GET /api/v1/agency/desks/SUPERVISOR-01` against that database. The desk was `SUPERVISOR-01`, status `disabled`, seven tools each `deny`, `can_enable` false, `running` false. The log was an empty list with `order_submitted` false. POST on both paths returned 405. `GET /api/v1/agents/{code}` is still not a path.
- The listener on `127.0.0.1:8000` (PID 11188) was not restarted. `GET /api/v1/agents` returned 200. The two new paths returned 404. Vite on 5173 was not restarted. A hot reload can show the new Audit section as unavailable until that API process is replaced. The success path was checked with the test client and Vitest, not in the browser against PID 11188.
- `DATABASE_URL=...@127.0.0.1:5433/veytrix VEYTRIX_ENV=local VEYTRIX_ENABLE_LIVE_BROKER=0 bash scripts/check.sh` exited 0. Ruff passed. Pytest: 256 passed, no skips. Web typecheck passed. Vitest: 196 passed. Vite build passed. Secret scan: `secret scan: no findings`. Docker was not started.
- Named tests: `test_audit_log_reads_local_postgres`, `test_audit_log_hides_a_row_that_claims_an_order`, `test_desk_detail_reads_the_local_registry`, `test_desk_detail_hides_a_desk_that_could_trade`, `test_agents_route_lists_disabled_desks_and_cannot_post`, `test_swap_ledger_respects_foreign_keys`, `test_swap_ledger_commits_on_local_postgres`.
- `services/ai-research/veytrix_ai/**` was not edited. No order route was added.
- Independent Codex review: not done. Item 15 in `docs/reviews/PENDING.md` is awaiting review.

Pros: the log and the desk page have no submit and no enable. Cons: there is still no auth, the process already on port 8000 does not serve the new paths, and one unsafe audit row hides the whole list. Confidence: high for the tests, the Postgres read, and the 404s. The live Audit page in the browser was not clicked.

## Verification, local API pass (8 November 2026)

- No new migration. Head stays `0009_agent_registry`. No `.env` was created. No Alpaca call: shell keys empty, no `.env`, and `~/.cursor/mcp.json` has no non-empty `ALPACA_API_KEY`. `SWAPBOT_PRIVATE_KEY` and `SWAPBOT_RPC_URL` are empty.
- `GET /api/v1/agents` and `GET /api/v1/system/status` were read against Postgres on `127.0.0.1:5433`. The registry returned the nine desks, all `disabled`, `trading_rights` denied, `agents_can_trade` false, `order_route` absent. `POST /api/v1/agents` returned 405.
- One `audit_events` insert for action `risk.size.recorded` was flushed on that database and rolled back. The payload’s `order_submitted` was false. No audit row was left behind.
- `DATABASE_URL=...@127.0.0.1:5433/veytrix VEYTRIX_ENV=local VEYTRIX_ENABLE_LIVE_BROKER=0 bash scripts/check.sh` exited 0. Ruff passed. Pytest: 245 passed, no skips. Web typecheck passed. Vitest: 191 passed. Vite build passed. Secret scan: `secret scan: no findings`. The script does not start servers. The API on port 8000 and Vite on 5173 were not restarted. Docker was not started.
- Named tests: `test_agents_route_lists_disabled_desks_and_cannot_post`, `test_agents_route_hides_a_desk_that_could_trade`, `test_agents_route_reads_the_local_registry`, `test_system_status_counts_desks_without_a_broker_balance`, `test_size_audit_row_inserts_and_rolls_back`, `test_event_contracts_cover_the_plan_and_are_not_routes`, `test_order_and_distribution_shapes_cannot_claim_execution`, `test_swap_ledger_respects_foreign_keys`, `test_swap_ledger_commits_on_local_postgres`, `test_alembic_upgrade_on_postgres_16`.
- The running dashboard at `http://127.0.0.1:5173/agency` showed the unavailable copy, because the API process was not restarted and does not have the new route. Market still showed a live Coinbase BTC-USD print. There is no enable or order control on the Agency page.
- `services/ai-research/veytrix_ai/**` was not edited. No order route was added.
- Independent Codex review: not done. Item 14 in `docs/reviews/PENDING.md` is awaiting review.

## Verification, registry pass (8 November 2026)

- Migration `0009_agent_registry` applied with `VEYTRIX_ENV=local` and `DATABASE_URL` on `127.0.0.1:5433`. Alembic reported head `0009_agent_registry`. A follow-up read showed 9 disabled agents, 63 deny permissions, RLS forced on the three private tables, and `security_invoker=true` on `public.agent_registry`. `mac01_state` still had its one row.
- `DATABASE_URL=...@127.0.0.1:5433/veytrix VEYTRIX_ENV=local VEYTRIX_ENABLE_LIVE_BROKER=0 bash scripts/check.sh` exited 0. Ruff passed. Pytest: 236 passed. Web typecheck passed. Vitest: 188 passed. Vite build passed. Secret scan: `secret scan: no findings`. The script does not start servers. The API on port 8000 and Vite on 5173 were not restarted. Docker was not started.
- Named tests: `test_agent_registry_migration_is_private_and_cannot_trade`, `test_alembic_upgrade_on_postgres_16`, `test_swap_ledger_respects_foreign_keys`, `test_swap_ledger_commits_on_local_postgres`. Outside CI, the Alembic test skips port 5432 so it cannot land on `daypilot-db`.
- No `.env` was created. No Alpaca call. No route was added. `services/ai-research/veytrix_ai/**` was not edited.
- Independent Codex review: not done. Item 13 in `docs/reviews/PENDING.md` is awaiting review.

Reference: PostgreSQL Global Development Group. (n.d.). Row security policies. In PostgreSQL 16 documentation. Retrieved 8 November 2026, from https://www.postgresql.org/docs/16/ddl-rowsecurity.html

## Verification, audit pass

- Read the plan, `CLAUDE.md`, the safety rule, the routers, MAC-01 config, and the stale READMEs.
- Called the local API. Did not restart it, Vite, or Docker. Did not create `.env`. Did not call Alpaca. Did not edit `services/ai-research/veytrix_ai/**` or `tests/test_swapbot*.py`.
- Secret scan: `.venv/bin/python scripts/scan_secrets.py` exited 0 with `secret scan: no findings`. `scripts/check.sh` was not run, because this pass is documentation. Ruff was not run, because no Python file was edited.
- Independent Codex review: not done.
