# Phase 0 baseline — 13 November 2026

This is the one implementation task after the audit. It records the checks that already exist. No test was weakened, skipped by editing, or deleted. No application code was changed. Phases 1–10 were not started.

Branch: `feature/phase-0-reconnaissance`. Worktree: `/Users/marcusbrown/Developer/veytrix`. The live sky view was not the code under test. Vite and the API were left running.

## Why this and not a feature

The first safe, dependency-ready gap is the mismatch between this branch and the live database. Fixing it means taking the preview's uncommitted migration `0012` and the schema that accepts `status = enabled`, then re-proving the trading flags stay false. That change belongs on the preview branch with its own review. Doing it here would either fork that work or hide the 503. Neither is safe in this pass.

## `bash scripts/check.sh`

Exit 1. Stopped at pytest because the script uses `set -e`. Ruff had already passed.

| Step | Result |
| --- | --- |
| `ruff check .` | Passed (`All checks passed!`) |
| `ruff format --check .` | Passed (150 files already formatted) |
| `pytest` | **2 failed, 319 passed, 1 skipped**, 7.71s. Python 3.14.6 from `.venv`. |
| Web typecheck, Vitest, build, secret scan | Not reached by `check.sh` |

The skip is `test_alembic_upgrade_on_postgres_16`. Outside CI the test refuses port 5432 because that port is `daypilot-db`. `DATABASE_URL` was unset in the shell, so the default URL contains `:5432/` and the test skipped. It did not create `veytrix_sprint0`.

### Failures

Both tests read `127.0.0.1:5433` and expect the registry this branch knows.

| Test | Expected | Actual |
| --- | --- | --- |
| `tests/test_agents_api.py::test_agents_route_reads_the_local_registry` | HTTP 200 and `status == disabled` | HTTP 503 |
| `tests/test_agents_api.py::test_desk_detail_reads_the_local_registry` | HTTP 200 and `status == disabled` | HTTP 503 |

Cause: Alembic on that database is `0012_enable_registry_status`, and every desk is `enabled`. `AgentDesk.status` on this branch is `Literal["disabled", "paused"]` (`services/api/veytrix_api/schemas.py`). Validation fails and `list_agents` returns 503 with `Agent registry is unavailable.` The running preview API, which is a different cwd, returns 200 for the same rows and keeps the four trading flags false.

The tests write nothing in the failing assertion. They were not changed.

## Steps run after `check.sh` stopped

Same commands the script would have run next, from this worktree:

| Step | Result |
| --- | --- |
| `npm --prefix apps/web run typecheck` | Passed |
| `npm --prefix apps/web test` | 40 files, 237 tests passed. jsdom warned that `HTMLCanvasElement.getContext` is not implemented. That warning is not a failed test. |
| `npm --prefix apps/web run build` | Passed. Largest chunks: `game` 1,202.60 kB (321.70 kB gzip), `index` 610.82 kB (178.91 kB gzip). Vite warned about chunks over 500 kB. |
| `scripts/scan_secrets.py` | `secret scan: no findings` |

`apps/web/dist` is build output. It is not part of the Phase 0 commit.

## Not run

| Check | Why |
| --- | --- |
| Preview worktree pytest / Vitest | That tree has no `.venv`. Its tests import the preview API. This `.venv` is an editable install of this checkout, so a preview run would mix trees. The preview also has uncommitted edits. They were left alone. |
| Coinbase ticker | Not required to explain the registry failure, and this pass avoided extra external calls. |
| Browser pass on `http://127.0.0.1:5173` | No UI code changed. Vite HTTP 200 only proves the dev server answered. |
| `pip-audit` and `npm audit` | Not part of `scripts/check.sh`. CI runs `npm audit`. Not run here. |
| GitHub Actions | Not pushed. |

## Safety

Live trading was not enabled. No order route was added. No Alpaca call was made. No migration was applied or reversed. No secret value was printed.
