# Branching

`main` is the integration branch. Day-to-day work happens on `feature/*`.

As of 8 November 2026 this clone is on `feature/sprint-0-foundation`, with no commits and no remote. `CODEOWNERS` has no GitHub login until a private remote exists.

- Do not commit directly to `main` or `master`.
- Do not force-push.
- Do not merge a pull request unless the repository owner asks.
- Sprint 0 lives on `feature/sprint-0-foundation`.
- A pull request waits until `main` exists on the remote. An empty local `main` with no commits is not a review base.

The GitHub repository is private. Do not add a public remote. Do not commit `.env`, keys, or service-account files.
