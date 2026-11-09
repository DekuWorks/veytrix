# Agent communication, Phase 0 report

Branch `feature/agent-communication`. Self-review by Claude. No independent review.

Shipped: `docs/phase-0/agent-communication-analysis.md` (agents, what was scripted, Supabase state, gaps, flags, rollback), five feature flags, the roster drift test (`tests/test_comms_roster.py`).

Findings that changed the plan:

1. No model and no worker exist, so a "real reply" can only be composed from local records and must say so.
2. The running API on port 8000 holds the sky-view code in memory; only the preview worktree contains both the sky view and this work. The API needs a restart from that worktree.
3. The sky view pairs Astra with `RESEARCH-01` and Dayvid with `DAY-01`. The Phase 0 branch says that pairing is unconfirmed.

Not done: nothing in this phase was deferred.
