# Phases 3 and 4: desk to desk, groups, boardroom

Scope delivered: `comms/discussion.py`, group routing and moderation in `routers/comms.py`.

Rules enforced in code and tested:

- Rounds 1 to 3, a message budget (40 for a discussion, 60 for a boardroom), and loop detection (a repeated message from the same desk stops the run and records `loop_detected`).
- A `claim` states how strong a desk's own evidence is: `supported`, `thin`, `unavailable`, or `abstain`. It is about evidence, not about trading.
- An `evidence` check must cite a trusted source the claim did not cite. Untrusted text (research notes) never counts. If a desk has none, it asks a `question`.
- A claim resting on fewer than two trusted sources draws an `objection`, threaded to the claim.
- Consensus is recorded only when an objection round ran, nothing is open, and two or more distinct trusted sources back the claims. Otherwise the Supervisor says "No consensus recorded" and why.
- The Supervisor writes dissent and unresolved questions, and proposes owners as `assignment` messages with status `proposed`. Nothing starts.
- Every recommendation says no order, transfer, or live-mode change can follow.
- Group rooms: the All desks room, custom groups, `@Name`, `@CODE`, `@all`, threads, unread counts, pause (messages are stored, desks do not reply), resume, redirect, assign owner, request evidence, close with a summary built from the stored rows.
- Boardroom: up to three agenda items, one status line per desk per item, an evidence tally, minutes. Off Wednesday it says it is off schedule.
- `POST /triggers` is gated by `autonomous_discussions` (off), with a 15 minute cooldown per task.

All discussion turns are `simulated`. No model is configured.

Tests: discussion and moderation sections of `tests/test_comms_api.py`, including controlled-fact engine tests for independence, untrusted text, open objections, budget, and loops.
