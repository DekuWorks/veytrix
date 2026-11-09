# Phase 0 completion report

Plan: `VEYTRIX_MASTER_CURSOR_TASKS.md` v1.0, Phase 0 (repository reconnaissance and requirements). Date: 9 November 2026. Branch `feature/phase-0-reconnaissance`, cut from `feature/sprint-0-foundation` at `5ef96c6`. Author: Claude, in Cursor. This is a self-review, not an independent review. Codex has not reviewed it.

The task file was read from the owner's Downloads folder. There is no copy at `docs/VEYTRIX_MASTER_CURSOR_TASKS.md`, so there was nothing to diff, and the Downloads file was followed. The task file did not name a path for Phase 0 output, so the docs went to `docs/phase-0/` and this report to `docs/reviews/`.

## What shipped

| Phase 0 task | Where | Status |
| --- | --- | --- |
| Inventory monorepo, framework versions, rendering engine, hosting, deployment, Supabase usage | `docs/phase-0/reconnaissance.md` §2 | Done |
| Inspect Sanctum animation, pathfinding, avatar positions, speech bubbles, conversation triggers, boardroom, activity feed | `reconnaissance.md` §3 | Done. Speech bubbles and conversation triggers do not exist yet; recorded, not invented. |
| Locate the authoritative registry; document names, ids, desks, roles, permissions without guessing | `docs/phase-0/agent-roster.md` | Done, with an open conflict (below) |
| Audit Alpaca, TradingView, WhatsApp, DayPilot, Claude/model and other integrations | `reconnaissance.md` §4 | Done |
| Inventory env vars and secrets without printing values; local, staging, paper, production boundaries | `docs/phase-0/environment.md` | Done. Presence checked as `SET`/`unset` only; all unset. |
| Architecture diagram, dependency map, feature inventory, risks, prioritised backlog, acceptance criteria | `reconnaissance.md` §5–9 | Done |
| Baseline performance, cost, security, accessibility, coverage metrics | `reconnaissance.md` §10 | Partly. Tests, build sizes, audits, secret scan, and cost recorded. Coverage, automated accessibility, and runtime performance were **not measured**: no tooling is installed and Phase 0 adds no dependencies. |
| Baseline tests (PR-01) | `tests/test_phase0_inventory.py` | Seven tests. The roster table must match migrations `0009` and `0010`, the web `AGENT_CODES`, and the Sanctum desk and boardroom tiles. The env table must list every variable the code reads. No `VITE_` name may look like a secret. Both drift checks were confirmed to fail on a mutated copy. |

Also: `docs/reviews/PENDING.md` item 30 queues this work for independent review.

## Deliberately not done

- **Feature flags.** PR-01 in the task file mentions them, but the Phase 0 checklist does not, and Phase 1 lists them explicitly. Adding a flag system now would be a runtime change with no feature to gate. Deferred to Phase 1.
- **No runtime code changed.** No API route, migration, web component, Sanctum file, MAC-01 file, swapbot file, or dependency was touched.
- **No 21st.dev component was read or used.** Phase 0 has no interface work.
- **No roster changes.** Astra, Dayvid, and Atlas (`LIEN-01`) were not added or mapped to a code. `FUTURES-01` was not removed.
- **No screenshots.** The UI did not change, and the browser was not opened in this pass.
- **No push, pull request, or merge.**
- `docs/architecture/current-state.md` and `docs/implementation-checklist.md` were not rewritten. Their stale points are listed in `reconnaissance.md` §1–2.

## Open questions for the owner

1. **Still open.** The task file says nine initial agents and Atlas as the tenth. The repository has ten desks (`FUTURES-01` was added on 9 November 2026). Is `FUTURES-01` intended, and is Atlas the eleventh?
2. Which existing desk code is "Astra" and which is "Dayvid"? Answered in part on 9 Nov 2026 (see below): they are existing desks, not new agents. The codes are still unassigned.
3. The blocking decisions already in `docs/implementation-checklist.md` still stand: Supabase organisation, region and cost; model provider and ids; regenerated Alpaca keys; DayPilot time and access.

## Owner decision, 9 Nov 2026

The owner confirmed one reading and nothing more: **Astra and Dayvid are names for desks that already exist. They are not new agents. Desk codes are not yet assigned.** The owner did not say which code is which, so none is recorded.

The task file uses the names in three lines, quoted as role hints only:

- Phase 6: "Give Astra read-only access to audit source-of-truth; store derived analysis separately with lineage and versioning."
- PR-06: "Astra audit-to-research feedback, citations, learning mode and Wednesday Boardroom prototype."
- Phase 10: "Implement Dayvid's DayPilot OAuth/service integration with narrow scopes, explicit write approval and duplicate-event prevention."

Any pairing of Astra or Dayvid with a desk code is **unconfirmed**. The nine-versus-ten question (`FUTURES-01`, and whether Atlas is the eleventh) is **still open**. No desk code, display name, registry row, or Sanctum tile changed.

## Independent review of `8b581bc`

An independent review approved `8b581bc` with nits. One nit was real: `docs/phase-0/environment.md` omitted `SWAPBOT_PRIVATE_KEY`, which `contracts/script/Deploy.s.sol` documents near line 14 and reads near line 43 with `vm.envUint`. **That omission is the fix in this commit.** The variable is now listed as a secret with no value. The doc states that this build does not deploy those contracts, and that the paper-swap CLI accepts no private key and refuses to run when one is present.

Changes made for the nit:

- `tests/test_phase0_inventory.py` now scans `contracts/**/*.sol` for `vm.env*` reads (`envOr`, `envUint`, `envString`, and the other `env*` cheatcodes). It skips `contracts/lib` (vendored, gitignored), `out`, `cache`, and `broadcast` (artefacts); the reason is written next to the pattern and in `environment.md`. No assertion was weakened or removed. Two tests were added: one for the Solidity scan, one that every documented `*PRIVATE_KEY`, `*MNEMONIC`, or `*SEED_PHRASE` name is classed as a secret.
- The wider scan found three other undocumented variables, all from `contracts/`: `SWAPBOT_VARIANT` (config, `Deploy.s.sol`), `SEPOLIA_RPC_URL` and `MAINNET_RPC_URL` (secret, `Fork.t.sol`; provider URLs often embed a key). They are in the inventory with descriptions taken from the code.

Drift-mutation check: the earlier claim that both drift checks fail on a mutated copy was made in the first commit. It was re-run for this commit on a temporary copy outside the repository, which was then deleted; the repository files were not touched. On that copy, removing the `SWAPBOT_PRIVATE_KEY` row failed three tests, adding an undocumented `vm.envString("NEW_UNDOCUMENTED_VAR")` to a `.sol` file failed two, and renaming a roster row to "Astra" failed the roster tests (with the earlier mutation still in place, so the count there is cumulative). The unmutated copy passed all seven tests.

Checks run for this commit: `pytest tests/test_phase0_inventory.py` (7 passed), `ruff check .` and `ruff format --check .` (clean), and `scripts/scan_secrets.py` (no findings). **Not run:** the full `bash scripts/check.sh`. A dev API (port 8000), the web dev server (5173), and Postgres (5433) were live, and port 5432 belongs to `daypilot-db`, so the full pytest suite and web build were skipped to avoid touching either. Run them before merge.

## How to verify

```bash
git switch feature/phase-0-reconnaissance
git diff --stat 5ef96c6..HEAD          # docs/, tests/test_phase0_inventory.py only
.venv/bin/pytest tests/test_phase0_inventory.py
bash scripts/check.sh
```

Then read `docs/phase-0/agent-roster.md` next to `services/api/alembic/versions/20261108_0009_agent_registry.py` and `apps/web/src/sanctum/floor.ts`.

## Risks

- The roster interpretation (nine plus `FUTURES-01`) could be wrong. The docs say so, and the test pins the code rather than an interpretation.
- The env inventory test finds variables by pattern (`AliasChoices`, `os.environ`, `os.getenv`, `import.meta.env`, `rpc_env_var`, Compose `${}`, Solidity `vm.env*`). A variable read some other way would slip past it.
- Baseline numbers were taken on Python 3.14.6; CI uses 3.12.
- The compromised Alpaca key pair is still the owner's to revoke.

## Safety statement

Live trading was not enabled. Bank transfers, payouts, and payment initiation were not enabled. No order route was added. `VEYTRIX_ENABLE_LIVE_BROKER` was not set. No Alpaca call was made. MAC-01 gates, caps, and tests were not changed. The swapbot was not run or changed. No LLM, prompt, or API route gained a path to an order or a swap. No secret value was read, printed, or committed. Sanctum agent names, desk positions, avatars, movement, boardroom gather and return, and the activity feed were not changed.
