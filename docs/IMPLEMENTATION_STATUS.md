# Implementation status

Date: 13 November 2026. Branch: `feature/sprint-0-stabilization` in `/Users/marcusbrown/Developer/veytrix-sanctum-preview`. The primary checkout `/Users/marcusbrown/Developer/veytrix` is still `feature/phase-0-reconnaissance` at `46d71d5` and was not edited. The `feature/worldview` stash was not applied or dropped.

## Verified this pass

- Skyview stays the HTML floor in the preview worktree. No Three.js, no new floor, no auth, no Supabase, no Alpaca, no YIELD row, and MAC-01 is still the SMA 20/50 rule.
- Alembic on `127.0.0.1:5433` was `0012_enable_registry_status` and is now `0013_research_tasks`. `upgrade head` was run. Port 5432 was not used. The dev database was not reset.
- Registry rows accept `enabled` for paper research. Trading flags stay false. `FUTURES-01` remains.
- `POST /api/v1/risk/size` was not given an order route. `execution_permitted` and `order_submitted` stayed false on the chat responses below. `mac01_orders` and `paper_positions` stayed at 0.

## Founder-to-Astra, 13 November 2026

`POST /api/v1/comms/conversations/{id}/messages` with “What are you working on?” returned HTTP 200.

- Origin stored: `model_generated`
- Model: `claude-haiku-4-5`
- Message id: `4d5e102b-fd07-4bd1-b503-850f336d936d`
- Reply: “No task is assigned to me right now. I'm standing by to read notes and source events on the research desk.”
- A second `GET` of that conversation returned the same message ids.
- After a refresh, the Sky View chat with Astra showed that sentence, labelled model, with diagnostics reporting `can_submit_orders` false. The floor still says live trading is disabled.

This was one streamed Anthropic Messages call. The browser receives the stored message after the stream finishes and shows a writing indicator. It does not paint tokens one by one.

## Roads assignment, 13 November 2026

`Have Astra and Cipher research NVIDIA.` returned HTTP 200.

- Task rows in `private.research_tasks`: `RESEARCH-01` and `DEFI-01`, subject `NVIDIA`, status `reported`, each with an evidence message id.
- Astra reply `bb93dcaf-7c3e-4050-bf9f-42af11502470` and Cipher reply `05306876-05eb-4498-9368-3e2a3a7ec315`, both origin `model_generated`. Both say no stored findings exist yet.
- Roads summary `7aa36ba7-0e52-48eb-8892-0e003f29b45c`, origin `tool_verified`. It quotes those stored replies and does not add a market fact.
- The Roads transcript was still there on refresh (`GET` HTTP 200, 9 messages in that existing direct chat). A group titled `Research: NVIDIA` is also stored.
- `ANTHROPIC_API_KEY` is present for the API process. The value was not printed and is not in git.

If the key is missing or the call fails, the stored origin is `tool_verified` or `scripted`, never `model_generated`. A greeting stays `scripted` and says Claude is offline when no key is set.

## Tests

From this worktree, with `DATABASE_URL` on `127.0.0.1:5433` and `VEYTRIX_ENABLE_LIVE_BROKER=0`. The key was unset for the suite.

| Check | Result |
| --- | --- |
| `ruff check` and `ruff format --check` | Passed |
| `pytest` | 451 passed, 0 failed, 0 skipped |
| `npm --prefix apps/web run typecheck` | Passed |
| `npm --prefix apps/web test` | 46 files, 286 passed |
| `npm --prefix apps/web run build` | Passed |
| `scripts/scan_secrets.py` | No findings |

## Not done

- Token-by-token text in the chat panel.
- Heartbeats, durable workers, auth, Supabase Realtime, and Alpaca paper.
- YIELD, EMA, live orders, and signing.

## Next executable task

Render the Anthropic stream into the open chat panel one chunk at a time, still one call per founder message, and keep `execution_permitted` false.
