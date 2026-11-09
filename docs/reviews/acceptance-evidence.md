# Acceptance evidence

Copy this into `docs/reviews/` under a dated filename when a phase claims a gate. Leave a field as "not run" rather than filling it from memory. Redact secrets before saving a response. An external integration is not complete until the proof row is filled from a real response.

```text
Phase:
Item:
Date:
Branch:
Author of the change:

Changed files:

Migration ids (or "none"):

Commands run, with exit codes:

Tests that passed (name the file). Tests not run:

External proof (broker id, HTTP status, calendar event id).
Paste a redacted response. "Unit test passed" is not external proof.

Screenshots or API responses (path). Secrets removed:

Security review (who, and what they looked at). "Not done" if Codex or another reviewer has not run:

Outstanding risks:

Rollback:

Owner approvals still required (keys, cost, paper order, live order, transfer):
```

Do not mark Paper Production or Live Production complete from this template alone. The definitions are at the end of the November 2026 master plan, and `docs/architecture/target-state.md` narrows them: AWS and Supabase are out until the owner approves the cost.
