# Agent communication

How the user talks to the ten Sanctum desks, and how desks talk to each other. Paper mode only. Nothing here can place an order, call MAC-01, run the swap CLI, sign, or move funds.

## What is real and what is labelled

No language model is configured, so no message is `model_generated`. Every message carries an origin, shown in the UI:

| Origin | Meaning | Used for |
| --- | --- | --- |
| `human` | You typed it. | Your messages. |
| `tool_verified` | Composed only from a read of local records, each cited. | Direct and group replies, closing summaries, minutes. |
| `scripted` | Fixed text. | Glossary entries, notices, "I'm not sure what you mean", pointers to another desk. |
| `simulated` | A fixed rule over the desk's own records. Not independent reasoning. | Discussion turns, recommendations, proposed tasks. |
| `model_generated` | A model wrote it. | Never written in this build. |

A desk that cannot read something says so. A failed read becomes an `unavailable` fact, not a guess.

## Architecture

```mermaid
sequenceDiagram
    participant U as You (Sanctum)
    participant API as FastAPI /api/v1/comms
    participant R as replies.py (read-only)
    participant DB as Postgres private.*
    participant RT as Supabase Realtime (optional)
    U->>API: POST /conversations/{id}/messages
    API->>DB: insert human message (seq n)
    API->>R: compose_reply(desk, text, history)
    R->>DB: read registry, ledger, notes (savepoint each)
    R-->>API: reply + citations + origin
    API->>DB: insert reply (seq n+1), events; commit
    API->>RT: doorbell {conversation_id, seq, message_id} (after commit; ids only)
    API-->>U: both messages
    U->>U: avatar speaks the stored reply
```

```mermaid
sequenceDiagram
    participant U as You
    participant API as POST /discussions
    participant E as discussion.py
    participant DB as Postgres
    U->>API: topic, rounds (1 to 3)
    API->>DB: conversation + members, your topic as message 1
    API->>E: run (budget 40 messages, loop detection)
    E->>DB: notice, claims, risk assessment, objections or checks, answers
    E->>DB: recommendation, proposed tasks, summary, close
    API-->>U: stored transcript
    U->>U: members walk to the boardroom, then speak in stored order
```

Trading events: there are none in this layer. `execution_facts` only reads `mac01_orders` and `paper_swap_fills`, and maps a row to `filled` only with a broker order id and a filled quantity.

## Data

Migration `0011_agent_comms`, schema `private`, RLS enabled and forced with the same local-role policy as the registry:

`conversations`, `conversation_members`, `messages` (append-only, unique `(conversation_id, seq)`), `message_events` (append-only), `agent_presence`, `conversation_summaries`.

Database constraints reject a human message with a non-human origin, an agent sender outside the ten codes, and content outside 1 to 4000 characters.

## API (all under `/api/v1/comms`)

`GET flags`, `GET roster`, `GET|POST conversations`, `GET|PATCH conversations/{id}`, `GET conversations/{id}/messages?after_seq&limit`, `POST conversations/{id}/messages`, `POST conversations/{id}/read`, `POST conversations/{id}/moderate`, `POST discussions`, `POST triggers` (flag `autonomous_discussions`, off), `GET feed`.

No path contains `order`, `trade`, or `execute`. A test fails if one is added.

## Settings

| Variable | Default | Purpose |
| --- | --- | --- |
| `VEYTRIX_FLAG_AGENT_CHAT` | on | Direct chat. |
| `VEYTRIX_FLAG_GROUP_CHAT` | on | Groups, discussions, boardroom. |
| `VEYTRIX_FLAG_AUTONOMOUS_DISCUSSIONS` | off | `POST /triggers`. 15 minute cooldown per task. |
| `VEYTRIX_FLAG_VOICE_CHAT` | off | Reserved. No voice code exists. |
| `VEYTRIX_COMMS_MESSAGES_PER_MINUTE` | 30 | Per client, per process. |
| `VEYTRIX_REALTIME_URL` | unset | Supabase URL for the server-side doorbell. https, or http on loopback. |
| `VEYTRIX_REALTIME_SERVER_KEY` | unset | Server-side key. Never a `VITE_` variable. Never logged. |

`live_execution` has no setting. It is a constant.

## Realtime

Unset URL or key: nothing is sent and the UI says "Supabase Realtime is not configured. Polling every 3 seconds." Set: after the commit the API posts a doorbell (ids only, no text) to the Supabase broadcast REST endpoint on topic `veytrix-comms`. The browser subscribes with the anon key (`VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`), then re-reads the message from this API. A failed publish is recorded as `realtime_failed` and never loses the message. No Supabase project is provisioned by this build. This path was tested with a fake transport only.

## Running it

The API on port 8000 loads code at start. To get these routes, restart it from this worktree and apply the migration:

```bash
cd /Users/marcusbrown/Developer/veytrix-sanctum-preview
export PYTHONPATH=services/api:services/market-data:services/risk:services/quant:services/ai-research
export VEYTRIX_ENV=local DATABASE_URL=postgresql+psycopg://veytrix:local-dev-only@127.0.0.1:5433/veytrix
/Users/marcusbrown/Developer/veytrix/.venv/bin/alembic -c services/api/alembic.ini upgrade head
/Users/marcusbrown/Developer/veytrix/.venv/bin/uvicorn veytrix_api.main:app --host 127.0.0.1 --port 8000
```

Until then the sky view says "Conversation API unavailable" and avatars stay silent.

## Rollback

`alembic downgrade 0010_futures_desk` drops the six tables. Revert the branch to restore the old bubbles. Turn a feature off with its flag.
