# Sanctum

Sanctum is a local sky-view of the ten registry desks. It lives on the existing Vite app at [http://127.0.0.1:5173/sanctum](http://127.0.0.1:5173/sanctum). It is not a separate app, and it is not a broker.

Production readiness is not met. There are no verified agent events, authentication is not implemented, and this build is not deployed.

## Startup

From the repository root, with the local database already listening on `127.0.0.1:5433`:

```bash
VEYTRIX_ENV=local DATABASE_URL=postgresql+psycopg://veytrix:local-dev-only@127.0.0.1:5433/veytrix \
  .venv/bin/uvicorn veytrix_api.main:app --host 127.0.0.1 --port 8000
```

```bash
npm --prefix apps/web run dev
```

Open `http://127.0.0.1:5173/sanctum`. The API should stay the only listener on `127.0.0.1:8000`. Do not use the DayPilot database on port 5432.

## Architecture

The page is a route in `apps/web`. Phaser 3 draws one continuous floor: stone tiles, neon trim, lounges, the Wednesday boardroom, and a workstation for each desk returned by `GET /api/v1/agents`. Sprites are generated in the browser. There is no asset CDN.

Desk status is polled from FastAPI (`/api/v1/agents`, the desk read, futures posture, the size audit, reconciliation, health, and the local reminder dates). Disabled desks with trading denied sit idle. A failed read is an error tint. The page does not invent a working trade.

Walking uses A* on the floor grid. Gathering desks in the boardroom is a local animation.

## Controls

- Sky View and Full Floor fit the whole headquarters.
- Floor View is a closer camera. Arrow keys or WASD move a visitor. Clicking a desk in this view follows that desk.
- Pan arrows, drag, wheel, zoom out, zoom in, and Fit move the camera.
- Center frames the globe. Meeting frames the boardroom. Trading frames the trading desks. None of these sends an order.
- Gather and Return, on the Boardroom rail item, walk the desks into the room and back. That is not a booked meeting.
- Clicking a desk opens a local detail panel. The note box stays in the browser. No model is called.

Sanctum has no order, enable, sign, withdraw, or Topstep control.

## What the panels mean

The chrome follows the sky-view reference. The counts do not. The registry currently reports every desk disabled and trading denied, so the status reads "Trading denied", active tasks stay "not verified", and verified trading stays "none verified" unless a reconciliation row really says `broker_confirmed`. No such row exists today. System health is the local API check, not a percentage.

The next Wednesday is computed on this machine in America/New_York. `GET /api/v1/treasury/reminders` supplies the accounting close and the payout review when that payload is the local calendar. It does not create a DayPilot event, and the meeting time stays unconfirmed.

## Authentication

Authentication is not configured. This local page is not an access control. Do not describe Sanctum as protected.

## Supabase

No Supabase project is provisioned by this build. The browser subscribes only when both `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` are set. The anon key is the public client key. Never put the service-role key in the frontend, in git, or in a `VITE_` variable. If either value is missing, or the key is a service-role key, Sanctum keeps polling FastAPI. A realtime payload cannot mark a trade as verified.

## Checks

```bash
npm --prefix apps/web run typecheck
npm --prefix apps/web test
```

Codex is not installed. An independent review is still outstanding. See `docs/reviews/PENDING.md`.
