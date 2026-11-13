# Integration status

Date: 13 November 2026. Checked against the preview API on `127.0.0.1:8000` and the Vite process on `127.0.0.1:5173`. No credential value is written here.

Env files `.env`, `.env.local`, and `.env.development` are ignored in both checkouts by `.gitignore` (`.env` and `.env.*`, with `!.env.example`). None of those files exist in either tree. A `.env.example` write was refused by the editor, so placeholders are in `config/runtime.example` only.

The API loads `.env` through Pydantic settings. The MAC-01 CLI loads the same file for `ALPACA_PAPER_API_KEY` and `ALPACA_PAPER_SECRET_KEY`. The browser reads only `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, and `VITE_SUPABASE_ANON_KEY`. Those three are unset in the running Vite process. No `VITE_` name in the web source is a server secret.

Git history: the only password-like assignment found in `docker-compose.yml` is the documented local placeholder or an interpolation. No Anthropic, Alpaca, or Supabase key assignment was found in history.

The Supabase CLI is already logged in. It listed projects. None is named Veytrix. No project was created.

| Service | Configured | Connection test | Remaining setup | Ready |
| --- | --- | --- | --- | --- |
| PostgreSQL (loopback) | yes | `GET /api/v1/ready` 200, database up. `GET /api/v1/agents` 200, 10 rows, trading flags false. | None for local development. Do not reset the database. | Development: yes. Paper: local only. |
| Claude (`ANTHROPIC_API_KEY`) | missing | not tested | Create a key at https://console.anthropic.com/settings/keys and put it in the gitignored `.env`. Do not paste it into chat. | Development: yes, simulated. Paper model: no. |
| Supabase server (`VEYTRIX_REALTIME_URL`, `VEYTRIX_REALTIME_SERVER_KEY`) | missing | not tested | Approve a new dedicated Veytrix project first. https://supabase.com/dashboard | No. |
| Supabase browser (`VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`) | missing | not tested | After that project exists, set only the public URL and anon key. Never a service-role key. | No. |
| Alpaca paper (`ALPACA_PAPER_API_KEY`, `ALPACA_PAPER_SECRET_KEY`) | missing | not tested | Create paper keys at https://app.alpaca.markets/paper/dashboard/overview and put those two names in `.env`. The CLI expects host `paper-api.alpaca.markets`. Do not use the live host. | Development: simulated orders. Paper execution: no. |
| Live brokerage | not enabled | not tested | Stays off. Do not set `VEYTRIX_ENABLE_LIVE_BROKER` or `MAC01_LIVE_CONFIRM`. | No. |

Development does not wait on the missing providers. They stay disconnected.
