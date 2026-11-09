# Agent communication, Phases 1 and 2 report

Shipped: migration `0011_agent_comms`, models, envelope, store, replies, facts, glossary, `routers/comms.py`, settings, CORS `PATCH`, OpenAPI snapshot, doc `docs/agent-communication/phase-1-2-direct-chat.md`.

Checks: `tests/test_comms_api.py`, `test_comms_logic.py`, `test_comms_roster.py`; `tests/test_schema.py` extended (exact table set and the RLS set now include the six new tables; nothing was removed or relaxed).

Bug found by the tests and fixed: a fact reader that failed rolled back the whole session and erased the user's pending message. Readers now run in savepoints, and one test fails if a reader raises on the migrated schema.

Not done: authentication (none exists in this build), retention, token streaming, cancel, secret encryption beyond an env-held server key.
