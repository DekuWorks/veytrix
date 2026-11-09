# Environment variables and boundaries

Phase 0 of `VEYTRIX_MASTER_CURSOR_TASKS.md` v1.0. Date: 9 November 2026.

No secret value was read or printed to write this file. Presence was checked with a shell test that reports only `SET` or `unset`. On this machine, in the shell used for the audit, every variable below was `unset`, and there is no `.env` file at the repository root or in `apps/web`. `tests/test_phase0_inventory.py` fails if code reads a variable this table does not list.

## Inventory

Class: **config** is safe to share, **secret** must never be committed or logged, **gate** is a deliberate safety switch.

| Variable | Read by | Class | Default or expected value | Notes |
| --- | --- | --- | --- | --- |
| `VEYTRIX_ENV` | API settings, Alembic, `infra/docker/api-entrypoint.sh` | gate | `local` | Any other value refuses boot. |
| `VEYTRIX_ENABLE_LIVE_BROKER` | API settings | gate | unset or `0` | Truthy refuses boot. Never set it. |
| `DATABASE_URL` | API settings, MAC-01 CLI, swapbot (via API settings) | secret | `postgresql+psycopg://veytrix:local-dev-only@127.0.0.1:5432/veytrix` | Host must be `127.0.0.1`, `localhost`, or `postgres`. On this machine the Veytrix database is port 5433; 5432 is `daypilot-db`. |
| `VEYTRIX_RATE_LIMIT_PER_MINUTE` | API settings | config | loopback default | Process-local limiter. |
| `VEYTRIX_LOG_LEVEL` | API settings | config | `INFO` | |
| `MAC01_LIVE_CONFIRM` | MAC-01 config; `services/api/veytrix_api/submission.py` (compare only) | gate | unset | `I_UNDERSTAND_REAL_MONEY` is one of eight live conditions. The API only compares it and never returns it. |
| `ALPACA_PAPER_API_KEY` | MAC-01 config | secret | unset | MAC-01 CLI only. The pair once pasted in chat is compromised and must be regenerated. |
| `ALPACA_PAPER_SECRET_KEY` | MAC-01 config | secret | unset | As above. |
| `ALPACA_LIVE_API_KEY` | MAC-01 config | secret | unset | Live. Keep separate from paper. Not needed for anything in Phase 0. |
| `ALPACA_LIVE_SECRET_KEY` | MAC-01 config | secret | unset | As above. |
| `SOLANA_DEVNET_RPC_URL` | `services/ai-research/swapbot.yaml` (`rpc_env_var`) | secret | unset | Testnet RPC. Provider URLs often embed an API key. |
| `ETHEREUM_SEPOLIA_RPC_URL` | `swapbot.yaml` | secret | unset | As above. |
| `BASE_SEPOLIA_RPC_URL` | `swapbot.yaml` | secret | unset | As above. |
| `VITE_API_BASE_URL` | `apps/web/src/api/client.ts`, `infra/docker/web.Dockerfile` | config | `http://127.0.0.1:8000` | Bundled into the browser. |
| `VITE_SUPABASE_URL` | `apps/web/src/pages/SanctumPage.tsx` | config | unset | Bundled into the browser. No Veytrix Supabase project exists. |
| `VITE_SUPABASE_ANON_KEY` | `SanctumPage.tsx` | config | unset | Public anon key only. `realtime.ts` refuses a service-role key. |
| `POSTGRES_PASSWORD` | `docker-compose.yml` | secret | `local-dev-only` | Placeholder for loopback Compose only. |
| `SWAPBOT_RPC_URL` | Comment in `contracts/script/Deploy.s.sol` | secret | unset | Foundry dry run only. Not run. Contracts are not deployed. |
| `CI` | `tests/` | config | `true` in GitHub Actions | Lets the schema tests use port 5432 in CI only. |

The swapbot also refuses to start when any variable ending in `PRIVATE_KEY`, `MNEMONIC`, or `SEED_PHRASE` holds a value (`veytrix_ai/guards.py`). Those are refusal patterns, not inputs.

Not present anywhere in the tree: a model provider key (Anthropic, OpenAI, or other), a WhatsApp or Twilio token, a DayPilot credential, a TradingView webhook secret, a Supabase service-role key, AWS credentials, and any bank or payment credential.

## Boundaries

| Environment | Exists? | How it is enforced today |
| --- | --- | --- |
| Local | Yes, on this machine | API boots only with `VEYTRIX_ENV=local` and a loopback database. Compose publishes on `127.0.0.1` only. |
| Paper | Partly | MAC-01 config defaults to `mode: paper`, `submit_orders: false`. No paper keys are configured, so no paper order can be sent. The API itself has no broker client. Swaps are simulated and testnet-only. |
| Staging | No | The API refuses any `VEYTRIX_ENV` other than `local`. There is no auth gateway, so a staging boot would be unsafe. Phase 1 lists a staging preview; it needs auth first. |
| Production | No | Same refusal. Not deployed. No hosting account in the tree. |
| Live (real money) | Code path exists, unused | MAC-01 CLI only, behind eight conditions in `services/quant/README.md`, $100 caps, and the kill switch. Not enabled and not reviewed (`docs/reviews/PENDING.md` item 11). |

## Rules for later phases

- A new secret goes in this table with its class before code reads it.
- No secret in a `VITE_` variable. Anything with that prefix is shipped to the browser. The inventory test rejects `VITE_` names containing `SECRET`, `SERVICE_ROLE`, `PRIVATE`, or `PASSWORD`.
- Paper and live broker keys stay in separate variables. The API process must never read either.
