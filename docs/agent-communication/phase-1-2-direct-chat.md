# Phases 1 and 2: messaging foundation and direct chat

Scope delivered: typed envelope (`comms/envelope.py`), store (`comms/store.py`), migration `0011`, desk reply composer (`comms/replies.py`), facts readers (`comms/facts.py`), glossary (`comms/glossary.py`), routes in `routers/comms.py`.

Behaviour:

- Every desk is reachable through `POST /conversations {kind: direct, agent_code}`. The same desk resumes the same conversation until you archive it.
- A message and its reply are stored in one transaction, ordered by `seq`, correlated by `correlation_id`, and deduplicated by `client_message_id`.
- Intents: what are you working on, show sources, explain this, why did you disagree, what actions were actually executed, define a term (beginner, intermediate, advanced), trade-like requests (refused with the registry's own denied-tool list), greetings, help, and a clarifying question when the text maps to nothing.
- A question outside the desk's records points to the desk that can read it.
- Research note titles and source events are quoted as untrusted data. Instruction-like text is withheld.
- Each reader runs in a savepoint. A failed read is an `unavailable` fact and does not undo the pending message rows.

Tests: `tests/test_comms_api.py` (database, 72), `tests/test_comms_logic.py` (pure, 42), `tests/test_comms_roster.py` (4).
