# Agent roster

Phase 0 of `VEYTRIX_MASTER_CURSOR_TASKS.md` v1.0. Date: 9 November 2026. Branch `feature/phase-0-reconnaissance`.

This is the roster as the repository defines it today. Nothing here was invented, renamed, or enabled. `tests/test_phase0_inventory.py` fails if this table drifts from the code.

## Sources of truth

| Layer | File | What it holds |
| --- | --- | --- |
| Database (authoritative) | `services/api/alembic/versions/20261108_0009_agent_registry.py` | Nine seeded rows in `private.agents`, seven `deny` permissions each. |
| Database | `services/api/alembic/versions/20261109_0010_futures_desk.py` | The tenth row, `FUTURES-01`, added disabled. |
| API | `GET /api/v1/agents`, `GET /api/v1/agency/desks/{code}` | Read-only. A row that could trade is not returned. |
| Web types | `apps/web/src/api/types.ts` (`AGENT_CODES`, `DENIED_TOOLS`) | The ten codes the browser accepts. |
| Sanctum floor | `apps/web/src/sanctum/floor.ts` (`DESK_TILES`, `BOARDROOM_SEATS`, `FLOOR_ORDER`) | Desk and boardroom tiles on the 60 × 42 grid. |
| Sanctum sprites | `apps/web/src/sanctum/sprites.ts` | One generated avatar per code. |

## Roster

Floor tile and boardroom seat are `x, y` on the Sanctum grid (16 px tiles).

| Code | Registry id | Display name | Desk (role) | Floor tile | Boardroom seat |
| --- | --- | --- | --- | --- | --- |
| `SUPERVISOR-01` | `a1000001-0000-4000-8000-000000000001` | Supervisor | `supervision` | 30, 23 | 24, 34 |
| `DAY-01` | `a1000002-0000-4000-8000-000000000002` | Day desk | `equities-session` | 16, 27 | 27, 34 |
| `STOCK-01` | `a1000003-0000-4000-8000-000000000003` | Stock desk | `equities-swing` | 16, 20 | 30, 34 |
| `CRYPTO-01` | `a1000004-0000-4000-8000-000000000004` | Crypto desk | `crypto-display` | 49, 10 | 36, 34 |
| `DEFI-01` | `a1000005-0000-4000-8000-000000000005` | DeFi desk | `simulated-swap` | 38, 11 | 27, 38 |
| `ETF-01` | `a1000006-0000-4000-8000-000000000006` | ETF desk | `etf` | 26, 9 | 33, 34 |
| `RESEARCH-01` | `a1000007-0000-4000-8000-000000000007` | Research desk | `research` | 16, 11 | 24, 38 |
| `RISK-01` | `a1000008-0000-4000-8000-000000000008` | Risk desk | `risk` | 48, 24 | 30, 38 |
| `TREASURY-01` | `a1000009-0000-4000-8000-000000000009` | Treasury desk | `treasury` | 44, 27 | 33, 38 |
| `FUTURES-01` | `a100000a-0000-4000-8000-00000000000a` | Futures desk | `futures-research` | 42, 20 | 36, 38 |

## Status and permissions (every row)

- `status` is `disabled`. The check constraint allows only `disabled` or `paused`.
- `paper_only` is true. `can_submit_orders`, `can_sign`, `can_transfer_funds`, and `holds_credentials` are false, and check constraints plus the `guard_agent_update` trigger stop them changing.
- Each desk has seven `deny` rows: `submit_order`, `cancel_order`, `sign_transaction`, `broadcast_transaction`, `bank_transfer`, `set_live_mode`, `release_kill_switch`. The permission table allows only `effect = 'deny'`.
- No desk runs a worker. `agent_runs` is empty unless something writes a row; nothing in the tree does.

## Owner decision, 9 Nov 2026

The owner confirmed one reading and nothing more: **Astra and Dayvid are names for desks that already exist. They are not new agents.** Desk codes are not yet assigned. The owner did not say which existing code is which, so this repository records no pairing.

The task file (`VEYTRIX_MASTER_CURSOR_TASKS.md` v1.0) uses the names in three lines. They are quoted here as role hints only:

- Phase 6: "Give Astra read-only access to audit source-of-truth; store derived analysis separately with lineage and versioning."
- PR-06: "Astra audit-to-research feedback, citations, learning mode and Wednesday Boardroom prototype."
- Phase 10: "Implement Dayvid's DayPilot OAuth/service integration with narrow scopes, explicit write approval and duplicate-event prevention."

What the hints do and do not say: Astra is attached to audit and research work, and Dayvid to DayPilot calendar work. Neither line names a code, a registry id, or a desk. Any pairing with a code in the table above is **unconfirmed** and is deliberately not made here. `tests/test_phase0_inventory.py` still fails if a roster row uses either name.

**Still open:** nine versus ten. The task file counts nine initial agents and Atlas (`LIEN-01`) as a later tenth. The repository has ten desks because `FUTURES-01` was added on 9 November 2026. The owner has not answered whether `FUTURES-01` is intended, or whether Atlas is the eleventh. Nothing was renamed, added, or removed.

## Conflicts with the master task file

1. **Nine versus ten (open).** The task file says "discover all nine initial agents" and calls Atlas (`LIEN-01`) a proposed tenth agent for about November 2027. The repository already has ten desks: the original nine from migration `0009` and `FUTURES-01` from migration `0010` (9 November 2026). This document treats the original nine as the "initial nine" and records `FUTURES-01` as an existing tenth desk. Atlas would therefore be the eleventh. The owner should confirm. Confidence: high for the counts, low for what the task file author meant.
2. **Persona names.** Resolved in part by the owner decision above: Astra and Dayvid are existing desks, not new agents. Which code each one is remains **unassigned**. Neither name appears in the code, migrations, or web app, and `docs/issue-board.md` row 06 says there is no "GPT Astra" id. No code is guessed here.
3. **Atlas / `LIEN-01`.** Absent. The `ck_agents_code` constraint would reject it. Not added.
