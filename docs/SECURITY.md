# Security

This sprint is a local research process, not a hardened service. The notes below say what is actually in place.

## What protects the machine

Compose publishes `5432`, `8000`, and `5173` on `127.0.0.1` only. Anyone who can already run code as the local user can call the API. That is not authentication. Diagnostics reports `auth: not_configured`, and the UI says the same thing.

The API refuses to boot outside that local posture, including when live broker mode is requested. Alembic refuses the same way. The database host must be loopback or the Compose name `postgres`.

CORS allows `http://127.0.0.1:5173` and `http://localhost:5173`, with credentials disabled. There are no cookies. A CSRF token is not implemented. When a session cookie is added later, the likely control is a same-site cookie plus a synchroniser token. That control does not exist yet.

## Secrets

`.env` is gitignored. The local database password in examples is `local-dev-only`. It is an obvious placeholder, not a production secret, and it must not be reused. `scripts/scan_secrets.py` allows that placeholder and fails on private keys, GitHub tokens, AWS access-key ids, live Stripe keys, and other URL passwords. `.gitleaks.toml` allowlists lines containing `local-dev-only` for people who run Gitleaks locally. That line allowlist would also ignore a real secret written on the same line, so do not do that. CI runs the Python scanner, which still flags key material on those lines.

Logs are JSON. They record method, path, status, duration, and correlation id. They do not record bodies or the database URL. Readiness errors do not include the driver exception text, because that text can contain the URL.

## Calculator

Risk fractions above 0.02 are rejected in code, not only in the database check. The stored policy cannot mark stops as enforced. The HTTP schema types `execution_permitted` and `order_submitted` as the constant `false`. The UI refuses to render a payload that claims otherwise.

## Not done

No MFA, no session, no distributed rate limit, no dependency pinning to commit SHAs for GitHub Actions, no formal penetration test, and no production network policy. The process-local rate limit is a brake on a buggy loop, not an access control.

Swagger UI is disabled so a browser does not load the API reference from a third-party CDN. The OpenAPI JSON is still available on the local API.

## Confidence

High that the API process cannot place an order: it has no order route, and it refuses to boot when live broker mode is set. Medium that a live Alpaca order is still possible from the MAC-01 command line if every condition in `services/quant/README.md` is met. That gate has not been used. No `.env` is in this tree, and a key pair pasted into a chat earlier is compromised. Medium that the loopback bind is the only network control: a local reverse proxy or a changed Compose file would remove it. Low that the dependency set is free of future advisories; the audit jobs exist so that question is re-checked, not answered forever.
