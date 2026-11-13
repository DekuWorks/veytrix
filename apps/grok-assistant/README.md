# Grok assistant

Separate from the Veytrix trading API. It does not import the quant package, the broker adapters, or the order routes.

The call shape follows the xAI Responses API: `POST /v1/responses` with `store: false`. The key is read from `XAI_API_KEY` in the process environment when you call `api_key_from_env()`. An empty value is reported as `unconfigured`. This build's default transport raises `OfflineError` and does not open a socket.

Per-user limits are in-memory and keyed by tenant plus user. Usage rows keep status and unit counts. They do not keep the prompt or the answer. Rows older than the retention window can be purged.

Do not create an xAI account from this repo, and do not commit a key.
