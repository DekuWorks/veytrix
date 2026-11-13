# Pending reviews

Claude Code has not reviewed this repository. Codex has not written or run tests. A Phase 00 inventory on 8 November 2026 (`docs/implementation-checklist.md`) is not that review. Nothing in this file is a finding from Claude or Codex. The checks below are unrun work for a later independent pass.

## 1. Sizing and the order boundary

- Scope: `services/risk/veytrix_risk/sizing.py`, `services/api/veytrix_api/routers/risk.py`, `tests/test_sizing.py`, `tests/test_api.py`
- Acceptance: the share count is `floor` of the minimum of the risk ratio and the allocation ratio; `float` inputs are rejected; a risk fraction above 0.02 is rejected; shorts are rejected; the response cannot set `execution_permitted` or `order_submitted` to true; the route writes no order.

## 2. Boot posture

- Scope: `services/api/veytrix_api/settings.py`, `services/api/alembic/env.py`, `tests/test_posture.py`
- Acceptance: live broker mode refuses to boot; a non-local environment refuses to boot; there is no auth-bypass flag; a remote database host refuses to boot; Alembic uses the same check.

## 3. Web accessibility and the synthetic chart

- Scope: `apps/web/src/shell`, `apps/web/src/pages`, `apps/web/src/components/SampleChart.tsx`
- Acceptance: skip link, visible focus, Escape closes the drawer, `aria-current` on the active link, Research and Audit are real pages, the synthetic SAMPLE banner is present, Coinbase products are labelled as a display, and a failed market request does not render a chart.

## 4. Supply chain and network bind

- Scope: `pyproject.toml`, `apps/web/package.json`, `docker-compose.yml`, `.github/workflows/ci.yml`, `infra/docker`
- Acceptance: alpaca-py is imported only by `alpaca_trading.py` and `alpaca_data.py`; no Vercel and no AWS credentials; host ports in `docker-compose.yml` are `127.0.0.1`; Lightweight Charts is the Apache-2.0 5.x library; CI can run from a fresh clone without cloud credentials. On this machine, host port 5432 is already taken by `daypilot-db`, and Veytrix Postgres is `127.0.0.1:5433`.

## 5. Schema baseline

- Scope: `services/api/veytrix_api/models.py`, `services/api/alembic/versions/20261107_0001_baseline.py`, `tests/test_schema.py`
- Acceptance for migration `0001`: the four baseline tables exist, exactly one paper policy is seeded, prices and instruments are not seeded, and the bar uniqueness constraint exists. Head is now `0009_agent_registry`, which was applied on `127.0.0.1:5433`. Review the later migrations on their own, including item 13. `alembic upgrade head` must still succeed on Postgres 16.

## 6. Licence carve-outs

- Scope: `docs/licenses/THIRD_PARTY.md`, `docs/licenses/DATA_SOURCES.md`, `apps/gods-eye/README.md`, `apps/web/src`
- Acceptance: God's Eye source is absent; the 21st.dev shell source is absent; the chart attribution names Lightweight Charts and not the proprietary Charting Library.

## 7. Swap helper contracts (audit)

- Scope: `contracts/src/MultiHopSwap.sol`, `contracts/src/MultiHopSwap02.sol`, `contracts/test`, `contracts/script/Deploy.s.sol`
- The paper-swap CLI does not sign or deploy these contracts. They are unaudited reference code.
- Acceptance: an independent audit with no open high or medium findings; `forge build` and `forge test` pass (they have not been run, because Foundry was not installed); both variants have identical checks apart from the router struct layout; there is no privileged role; allowances return to 0; there is no ETH or token residue; the deploy script refuses non-testnet chains.

## 8. Fork tests against the real routers

- Scope: `contracts/test/Fork.t.sol`
- Acceptance: the Sepolia fork (SwapRouter02) and mainnet fork (original SwapRouter) tests pass against Uniswap's published deployments; multi-hop, ETH in, and ETH out are covered; nothing is broadcast.

## 9. Simulated paper swaps

- Scope: `services/ai-research/veytrix_ai`, `services/ai-research/swapbot.yaml`, `services/api/alembic/versions/20261108_0008_paper_swaps.py`, `services/api/veytrix_api/routers/paper_swaps.py`, `tests/test_swapbot.py`
- Acceptance: the CLI cannot sign or broadcast; mainnet chain ids and mainnet RPC URLs are refused; an unknown chain is refused; an insufficient simulated balance is refused; slippage is applied with `Decimal`; receipts are labelled simulated and include the quote source, quoted price, fee estimate, and balances; no config field or module accepts a private key; the kill switch blocks a swap before any market-data call; the API routes are GET only and do not import the CLI. Live stock trading stays behind the MAC-01 gate. A quote against a real RPC has not been run.

## 10. Mainnet review (blocked)

- Scope: any future live chain
- Acceptance: do not add a mainnet chain id. This build has no signing path and no hot-wallet key. A later design would need a separate review before any broadcast existed. Live stock orders remain the MAC-01 gate in item 11, not this CLI.

## 11. MAC-01 live gate (before the first live order)

- Scope: `services/quant/veytrix_quant/mac01` (`config.py`, `engine.py`, `alpaca_trading.py`, `alpaca_data.py`, `ledger.py`, `__main__.py`), `config/mac-01.yaml`, `services/api/alembic/versions/20261108_0007_mac01_ledger.py`, `tests/test_mac01_*.py`
- Acceptance: an independent reviewer confirms that live submission is impossible unless every one of the eight conditions in `services/quant/README.md` holds; that each has a failing-first test; that a buy can never exceed $100 notional or push the position above $100; that a sell only closes a held long quantity; that a timeout is looked up and never retried; that alpaca-py retries are off and a request timeout is set; that keys never reach logs, the ledger, or reprs; and that no API route, model, or page can reach `Mac01Engine.run`.
- Also: run one paper `run --submit` during regular hours and one live dry run against the real account (account-number match only, no order) before the first live `--submit`. Neither has been done; no `.env` with keys exists in this tree.

## 12. MAC-01 deviation: sell is a quantity order, not `close_position`

- Scope: `engine.py`, `alpaca_trading.py`
- Acceptance: the reviewer agrees that a market DAY sell of the held quantity, with a deterministic `client_order_id`, is a better fit than `TradingClient.close_position`. `close_position` takes no `client_order_id`, so a timed-out close could not be looked up and might be sent twice. If the reviewer disagrees, switch and add the lookup another way.

## 13. Local agent registry (awaiting review)

- Scope: `services/api/alembic/versions/20261108_0009_agent_registry.py`, `services/api/veytrix_api/models.py`, `tests/test_schema.py`
- Status: implemented on 8 November 2026. Codex has not reviewed it. Do not treat the checklist ticks as a closed gate.
- Acceptance: schema `private` is revoked from `PUBLIC`; the nine desks are seeded disabled; no row can submit, sign, transfer, or hold credentials; every permission effect is `deny`; `audit_events` and the run and permission tables reject update, delete, and truncate; `public.agent_registry` is `security_invoker`; RLS on the three private tables hides rows from a non-owner role; existing public tables were not moved. The original pass added no API route. A later pass added `GET /api/v1/agents`; review that under item 14. The reviewer should also say whether a superuser `veytrix` role makes the RLS policies moot until a non-superuser login exists.

## 14. Registry read, size audit, and event shapes (awaiting review)

- Scope: `services/api/veytrix_api/routers/agents.py`, `services/api/veytrix_api/routers/system.py`, `services/api/veytrix_api/routers/risk.py`, `services/api/veytrix_api/audit_log.py`, `services/api/veytrix_api/events.py`, `services/api/veytrix_api/schemas.py`, `apps/web/src/pages/AgencyPage.tsx`, `tests/test_agents_api.py`, `tests/test_events.py`
- Status: implemented on 8 November 2026. Codex has not reviewed it. Do not treat the checklist ticks as a closed gate.
- Acceptance: `GET /api/v1/agents` is the only agents method; a desk that could submit, sign, transfer, or hold credentials is not returned; `POST /api/v1/risk/size` writes one append-only audit row with the correlation id and `order_submitted` false, and writes none when the size is rejected; event models are not routes and cannot describe a live order or an executed transfer; the Agency page has no enable or order control; no order route was added; `services/ai-research/veytrix_ai/**` was not changed.

## 15. Audit log read and desk detail (awaiting review)

- Scope: `services/api/veytrix_api/routers/audit.py`, `services/api/veytrix_api/routers/agency.py`, `services/api/veytrix_api/schemas.py`, `apps/web/src/pages/AuditPage.tsx`, `apps/web/src/pages/AgencyPage.tsx`, `tests/test_audit_log.py`, `tests/test_agents_api.py`
- Status: implemented on 8 November 2026. Codex has not reviewed it. Do not treat the checklist notes as a closed gate.
- Acceptance: `GET /api/v1/audit/log` is the only method on that path; it returns size-audit rows and nothing else; a payload that claims `order_submitted`, adds an unknown key, or uses another action returns 503 and does not echo the row; `GET /api/v1/agency/desks/{code}` cannot enable a desk; a desk that could submit, or a permission that is not deny, returns 503; `POST` on either path is 405; `/api/v1/agents/{code}` is still absent; no order route was added.

## 16. Monthly distribution projection (awaiting review)

- Scope: `services/risk/veytrix_risk/treasury.py`, `services/api/veytrix_api/routers/treasury.py`, `services/api/veytrix_api/schemas.py`, `apps/web/src/pages/TreasuryPage.tsx`, `tests/test_treasury.py`, `tests/test_treasury_api.py`
- Status: implemented on 8 November 2026. Codex has not reviewed it. Do not treat the checklist notes as a closed gate.
- Acceptance: the proposal is half of positive eligible profit after cents rounding, capped at `$2,000.00`, and zero when eligible profit is not positive; a loss carries forward only inside the pure function, because the route does not store one; `GET /api/v1/treasury/monthly-summary` is the only method on that path; it reads paper MAC-01 fills and returns 503 for live mode, a sell without a buy, or a down database; `transfer_submitted`, `settled`, and `broker_reconciled` stay false; POST is 405; `POST /api/v1/treasury/distributions/{id}/approve` is not a route; the Treasury page has no approve or payout control; no order route was added; `services/ai-research/veytrix_ai/**` was not changed.

## 17. Market-feed health and the System page (awaiting review)

- Scope: `services/market-data/veytrix_market/health.py`, `services/api/veytrix_api/routers/market.py`, `services/api/veytrix_api/schemas.py`, `apps/web/src/pages/SystemPage.tsx`, `tests/test_market_health.py`
- Status: implemented on 8 November 2026. Codex has not reviewed it. Do not treat the checklist notes as a closed gate.
- Acceptance: `GET /api/v1/market/health` is the only method on that path; the three products stay in display order; a print older than 120 seconds is `stale` and a print at 120 seconds is still `up`; a down feed has a null price, timestamp, and age; the overall status is `ok` only when every feed is up, and `unavailable` only when every feed is down; `executable`, `execution_permitted`, and `order_submitted` stay false; SAMPLE is not a feed; the System page hides a posture that says a desk can trade and hides a feed list that says an order was submitted; a failed market read does not remove the local posture; no order route was added.

## 18. Settings page (awaiting review)

- Scope: `apps/web/src/pages/SettingsPage.tsx`, `apps/web/src/App.tsx`, `apps/web/src/shell/AppShell.tsx`
- Status: implemented on 8 November 2026. Codex has not reviewed it. Do not treat the checklist notes as a closed gate.
- Acceptance: the page reads `GET /api/v1/diagnostics` and nothing else; it renders no text field, switch, or save control; a payload that sets `execution_permitted` true is not shown; a failed read does not invent a live switch; no API route was added.

## 19. Local shield preview (awaiting review)

- Scope: `services/risk/veytrix_risk/shield.py`, `services/api/veytrix_api/routers/risk.py`, `services/api/veytrix_api/schemas.py`, `tests/test_shield.py`, `tests/test_shield_api.py`
- Status: implemented on 8 November 2026. Codex has not reviewed it. Do not treat the checklist notes as a closed gate.
- Acceptance: `POST /api/v1/risk/shield/preview` is the only method on that path; a `$100.00` AAPL buy can pass the local rule and still return `release` `withheld`, `buying_power_checked` false, `owner_approved` false, and `execution_permitted` false; a short, leverage other than 1, a symbol other than AAPL, a quote older than 120 seconds, a notional above `$100`, a position that would finish above `$100`, and a third order today fail together; a quote aged 120 seconds still passes; a JSON number is 422; the route does not need the database; GET is 405; no order id is returned; no order route was added; `services/ai-research/veytrix_ai/**` was not changed.

## 20. Local reservation preview (awaiting review)

- Scope: `services/risk/veytrix_risk/reservation.py`, `services/api/veytrix_api/routers/risk.py`, `services/api/veytrix_api/schemas.py`, `tests/test_reservation.py`, `tests/test_reservation_api.py`
- Status: implemented on 8 November 2026. Codex has not reviewed it. Do not treat the checklist notes as a closed gate.
- Acceptance: `POST /api/v1/risk/reservations/preview` is the only method on that path; a request that keeps the caller-supplied book at or under `$100.00` can pass and still return `release` `withheld`, `persisted` false, `lock` `absent`, `buying_power_checked` false, and `execution_permitted` false; the same idempotency key is not added twice; a second key for the same desk fails; an unknown desk, a reused key, and a total above `$100` fail together; two previews that do not list each other can both pass; a JSON number is 422; the route does not call `size_position` and does not need the database; GET is 405; no order id is returned; no order route was added; `services/ai-research/veytrix_ai/**` was not changed.

## 21. Supervisor tool catalogue (awaiting review)

- Scope: `services/api/veytrix_api/tool_gate.py`, `services/api/veytrix_api/routers/supervisor.py`, `services/api/veytrix_api/schemas.py`, `apps/web/src/pages/SupervisorPage.tsx`, `tests/test_tool_gate.py`, `tests/test_supervisor_api.py`
- Status: implemented on 8 November 2026. Codex has not reviewed it. Do not treat the checklist notes as a closed gate.
- Acceptance: `GET /api/v1/supervisor/tools` is the only method on that path; every tool has `executes` false; `chat` is `absent` and `model` is `not_configured`; `POST /api/v1/supervisor/tools/check` can accept a read with the expected strings and still return `executed` false; a hidden instruction, an unknown name, `submit_order`, and `size_position` are denied; the check does not call `size_position`; a JSON number is 422; GET on the check path is 405; `POST /api/v1/supervisor/chat` is not a route; the Supervisor page has no text field, switch, or run button, and it hides a tool that claims to execute; no order route was added; `services/ai-research/veytrix_ai/**` was not changed.

## 22. Local reminder dates (awaiting review)

- Scope: `services/risk/veytrix_risk/treasury.py`, `services/api/veytrix_api/routers/treasury.py`, `services/api/veytrix_api/schemas.py`, `tests/test_treasury.py`, `tests/test_reminders_api.py`
- Status: implemented on 8 November 2026. Codex has not reviewed it. Do not treat the checklist notes as a closed gate.
- Acceptance: `GET /api/v1/treasury/reminders` is the only method on that path; the accounting close is the 1st of the next month and the payout review is the 5th, with Saturday and Sunday moved to Monday; `daypilot` stays `absent`; `event_created` stays false; `meeting_time` stays `unconfirmed`; `transfer_submitted` stays false; POST is 405; `GET /api/v1/meetings` is not a route; the route does not need the database; no DayPilot event is created; no order route was added; `services/ai-research/veytrix_ai/**` was not changed.

## 23. Scheduler status (awaiting review)

- Scope: `services/api/veytrix_api/routers/strategies.py`, `services/api/veytrix_api/schemas.py`, `apps/web/src/pages/SchedulePage.tsx`, `tests/test_schedule_api.py`
- Status: implemented on 8 November 2026. Codex has not reviewed it. Do not treat the checklist notes as a closed gate.
- Acceptance: `GET /api/v1/strategies/mac-01/schedule` is the only method on that path; the clock is 09:35 America/New_York and the delay is five minutes; `calendar` stays `not_read` and `next_session` stays `unknown`; `running`, `submit_flag`, `can_start`, and `alpaca_called` stay false even when the config says live and `submit_orders`; an unsafe config still cannot start; POST is 405; there is no start route; the page has no start control and hides a payload that says the scheduler can start; no order route was added; `services/ai-research/veytrix_ai/**` was not changed.

## 24. Live-gate evidence (awaiting review)

- Scope: `services/api/veytrix_api/submission.py`, `services/api/veytrix_api/routers/system.py`, `services/api/veytrix_api/schemas.py`, `apps/web/src/pages/LiveGatePage.tsx`, `tests/test_submission_api.py`
- Status: implemented on 8 November 2026. Codex has not reviewed it. Do not treat the checklist notes as a closed gate. This is not the review named in item 11.
- Acceptance: `GET /api/v1/system/submission` is the only method on that path; the eight condition names stay in order; `submit_flag`, `account_match`, `account_active`, and `kill_switch_off` stay unmet; `live_submission_possible`, `paper_submission_from_api`, `api_reaches_engine`, and `broker_called` stay false even when the config says live and the confirmation phrase matches; the phrase and the account number are not in the body; a wrong phrase is not echoed; an unsafe config meets nothing; POST is 405; the page has no switch and hides a payload that says live submission is possible; no order route was added; `services/ai-research/veytrix_ai/**` was not changed.

## 25. Local reconciliation (awaiting review)

- Scope: `services/api/veytrix_api/routers/reconciliation.py`, `services/api/veytrix_api/schemas.py`, `apps/web/src/pages/ReconciliationPage.tsx`, `tests/test_reconciliation_api.py`
- Status: implemented on 8 November 2026. Codex has not reviewed it. Do not treat the checklist notes as a closed gate. This is not an Alpaca reconciliation.
- Acceptance: `GET /api/v1/ledger/reconciliation` is the only method on that path; `broker_read` stays `absent`; `reconciled`, `alpaca_called`, and every row's `matched` stay false; `broker_status` stays `not_read` even when a broker id is stored; an unknown status or a failed session returns 503 and no rows; the terminal status set matches the MAC-01 ledger; POST is 405; `GET /api/v1/broker/paper/account` is not a route; the page has no reconcile control and hides a payload that says the book is reconciled; no order route was added; `services/ai-research/veytrix_ai/**` was not changed.

## 26. Risk event log (awaiting review)

- Scope: `services/api/veytrix_api/routers/risk.py`, `services/api/veytrix_api/schemas.py`, `apps/web/src/pages/RiskLogPage.tsx`, `tests/test_risk_events_api.py`
- Status: implemented on 8 November 2026. Codex has not reviewed it. Do not treat the checklist notes as a closed gate.
- Acceptance: `GET /api/v1/risk/log` is the only method on that path; it returns size-audit rows and nothing else; shield and reservation previews are named and `persisted` stays false; a payload that claims `order_submitted` returns 503 and does not echo the row; the route writes no row; POST is 405; no path ends in `/events`; the page has no submit control and hides a preview marked stored; no order route was added; `services/ai-research/veytrix_ai/**` was not changed.

## 27. Paper-swap posture (awaiting review)

- Scope: `services/api/veytrix_api/routers/paper_swaps.py`, `services/api/veytrix_api/schemas.py`, `apps/web/src/pages/PaperSwapsPage.tsx`, `tests/test_paper_swap_posture.py`
- Status: implemented on 8 November 2026. Codex has not reviewed it. Do not treat the checklist notes as a closed gate.
- Acceptance: `GET /api/v1/paper-swaps/posture` is the only method on that path; signing and broadcast stay `absent`; the private key and mainnet stay `refused`; `api_can_record` stays false; the networks stay Solana devnet, Sepolia `11155111`, and Base Sepolia `84532`; the route does not import `veytrix_ai` and does not need the database; POST is 405; portfolio and orders stay GET only; the page hides a posture that says the API can record; no order route was added.

## 28. Disabled FUTURES-01 posture (awaiting review)

- Scope: `services/api/alembic/versions/20261109_0010_futures_desk.py`, `services/api/veytrix_api/routers/futures.py`, `services/api/veytrix_api/schemas.py`, `apps/web/src/pages/FuturesPage.tsx`, `tests/test_futures_posture.py`, `tests/test_schema.py`
- Status: implemented on 9 November 2026. Codex has not reviewed it. Do not treat the checklist notes as a closed gate. This is not a Topstep connection.
- Acceptance: migration `0010_futures_desk` adds one disabled desk and seven deny permissions; `can_submit_orders`, `can_sign`, `can_transfer_funds`, and `holds_credentials` stay false; `GET /api/v1/futures/posture` is the only method on that path; Topstep automation stays `disabled`; the account stays `not_connected`; orders stay `absent`; market data stays `not_read`; `execution_permitted` and `order_submitted` stay false; POST is 405; there is no futures order route; the page has no enable or order control and hides a payload that says execution is permitted; no Alpaca call; `services/ai-research/veytrix_ai/**` was not changed.

## 29. Sanctum floor (awaiting review)

- Scope: `apps/web/src/pages/SanctumPage.tsx`, `apps/web/src/sanctum/`, `apps/web/src/App.tsx`, `apps/web/src/shell/AppShell.tsx`
- Status: implemented on 9 November 2026. Codex is not installed and has not reviewed it. Do not treat this note as a closed gate. Production readiness is not met: no verified agent events, no auth, no deployment. Supabase was not provisioned.
- Acceptance: `/sanctum` is one Phaser floor for the ten registry desks; sky, floor, pan, zoom, centre, meeting, and trading cameras do not submit an order; NPC pose comes from `GET /api/v1/agents` and stays idle while the desks are disabled and trading is denied; verified trading stays "none verified" unless a row says broker-confirmed; the local note box does not call a model; the service-role key is not read by the page; there is no order, enable, sign, withdraw, or Topstep control.

## 30. Phase 0 reconnaissance (awaiting review)

- Scope: `docs/phase-0/reconnaissance.md`, `docs/phase-0/agent-roster.md`, `docs/phase-0/environment.md`, `docs/reviews/phase-0-completion.md`, `tests/test_phase0_inventory.py`
- Status: written on 9 November 2026 against `VEYTRIX_MASTER_CURSOR_TASKS.md` v1.0. Self-reviewed by the author only. Codex has not reviewed it.
- Acceptance: the roster lists exactly the ten codes in migrations `0009` and `0010` with matching ids, display names, desks, and Sanctum tiles; Astra, Dayvid, and Atlas are not mapped to a code; the env table lists every variable the code reads and prints no value; no `VITE_` variable looks like a secret; integration statuses match the routers and tests cited; baseline metrics that were not measured say so; no runtime file changed; no order route was added; `services/ai-research/veytrix_ai/**` was not changed.

## 31. Agent communication (awaiting review)

- Scope: `services/api/veytrix_api/comms/`, `services/api/veytrix_api/routers/comms.py`, `services/api/alembic/versions/20261109_0011_agent_comms.py`, `apps/web/src/comms/`, `apps/web/src/sanctum/ui/Chat*.tsx`, `ConversationMonitor.tsx`, `SkyFloor.tsx`, `tests/test_comms_*.py`
- Status: implemented on 9 November 2026 by Claude. Not independently reviewed. No language model is configured; every discussion turn is `simulated`. Supabase Realtime was not provisioned and the doorbell was tested with a fake transport only.
- Acceptance: all ten desks answer and persist; no `comms` module imports MAC-01, alpaca, or `veytrix_ai`, or constructs an order row; no route name contains order, trade, or execute; `live_execution` is a constant false; `filled` appears only with a broker order id and a filled quantity; a repeated message stops a discussion; consensus needs an objection round and two distinct trusted sources; untrusted text never counts as a source; messages and events reject update and delete; the Realtime payload carries no message text.

