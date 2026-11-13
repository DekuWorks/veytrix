# Trading tools and public assistants

Written 13 November 2026 against commit `b329141` (`feature/sprint-0-stabilization`), then implemented on `feature/trading-tools-and-assistants`. This file describes the tree that was read and the paper-only slice added beside it.

`docs/architecture/current-state.md` is an 8 November audit. It says the repository had no commits. That is no longer true. Use this file for the tool boundaries, and `docs/architecture.md` for the HTTP sketch.

Confidence is high for files opened in this commit and for the provider pages fetched the same day. It is medium where a vendor page describes a click-path without a developer reference. It is low for any price, fill, or account state: this pass did not call a broker and did not invent one.

## What the repository actually is

Veytrix is a local research desk for one person. The API binds for `VEYTRIX_ENV=local` only. It refuses to boot when `VEYTRIX_ENABLE_LIVE_BROKER` is set, when the environment is not `local`, or when the database host is not `127.0.0.1`, `localhost`, or `postgres`. Authentication and CSRF are not implemented. The rate limit is process-local.

| Piece | Role |
| --- | --- |
| `apps/web` | Vite + React dashboard. Charts use TradingView Lightweight Charts `5.2.1`. They plot bars the API returned. |
| `services/api` | FastAPI under `/api/v1`. `POST /api/v1/risk/size` returns a long-only share count with `execution_permitted` and `order_submitted` false. There is no order route. |
| `services/market-data` | In-memory synthetic `SAMPLE`, plus public Coinbase candles for `BTC-USD`, `ETH-USD`, and `SOL-USD`. A failed fetch is not replaced with a made-up price. |
| `services/risk` | Decimal sizing, shield, reservation, treasury. These calculate. They do not submit. |
| `services/quant/veytrix_quant/mac01` | The only broker order path. The decider is the AAPL daily SMA 20/50 crossover. Orders come from `python -m veytrix_quant.mac01 run --submit` or `schedule --submit`. |
| `services/ai-research` | Simulated paper-swap CLI. It does not sign or broadcast. The API can read the rows and cannot submit a swap. |
| `services/execution` | Was a placeholder. This slice adds in-memory paper recorders. The API does not import them. |
| `services/event-intelligence`, `services/portfolio` | README-only. Paper positions shown by the API are not broker fills. |
| `contracts/` | Unaudited Foundry helpers. Not deployed. |
| `apps/gods-eye` | Notes for a later fork. No upstream trading code. |
| `apps/obsidian-assistant`, `apps/grok-assistant` | Separate apps added in this slice. They do not import the trading packages. |

Tests live in `tests/` and run from `scripts/check.sh` (ruff, pytest, the web typecheck, Vitest, the web build, and `scripts/scan_secrets.py`). The OpenAPI snapshot test fails if a route is added without regenerating `packages/shared/openapi.json`. This slice does not add an HTTP route, so that snapshot stays as it was.

Alembic revisions in the tree run through `services/api/alembic/versions/20261113_0014_worker_tasks.py`. This pass did not migrate a database.

### Live gate

MAC-01 live submission still needs all eight conditions in `services/quant/README.md`: config `mode: live`, `live_enabled: true`, `submit_orders: true`, `MAC01_LIVE_CONFIRM=I_UNDERSTAND_REAL_MONEY`, CLI `--submit`, an `expected_account_number` that matches the account, an unblocked `ACTIVE` account, and the kill switch off. Caps stay at $100 notional, $100 position, 2 orders a day, one open order, long only. alpaca-py may be imported only by `alpaca_trading.py` and `alpaca_data.py`.

The API may import `veytrix_quant.mac01`, `config`, and `strategy`. It may not import the engine, the ledger, or the adapters. `tests/test_contract.py` locks that.

### Market data that exists

- `SAMPLE` at venue `SIM`: seeded weekday bars, source `synthetic-sample`. Not a market price.
- Coinbase Exchange public candles and last trade for three products, source `coinbase-exchange`. Display only.
- MAC-01 can request AAPL daily bars from Alpaca when the operator runs the CLI. That path is not the chart's source, and this pass did not run it.

### Market data that does not exist

No TradingView quote feed. No TradersPost, SignalStack, or Market Gear price feed. No options chain. No equity ticker in the API other than the synthetic sample. Futures posture is a disabled statement, not a price. Nothing in the new recorders fills a missing price.

## Staged plan

| Stage | Scope | State |
| --- | --- | --- |
| 0 | Document the tree. Add disabled paper recorders, a CLI checklist, and two separate assistants. No HTTP ingress, no broker call, no account creation. | This worktree. |
| 1 | You create vendor accounts yourself and keep paper and live keys apart. | Manual. Not done. |
| 2 | A loopback webhook receiver. | Not started. The API has no auth, so an open receiver would be an order-shaped inbox. It needs its own design and review. |
| 3 | Live routing. | Not an extension of this slice. ADR 0001 rejected a broker hidden behind a flag. |

## TradingView

Lightweight Charts is a chart library (Apache-2.0). It draws bars. It does not receive alerts and it is not a broker. `apps/web` keeps `lightweight-charts` `5.2.1`. The library was not swapped.

TradingView's webhook document describes a different product. When an alert fires, TradingView sends an HTTP POST. The body is the alert message. Valid JSON is sent as `application/json`. Other messages are `text/plain`. The documented timeout is 3 seconds. Only ports 80 and 443 are accepted. Webhooks require 2-factor authentication on the TradingView account. The message has no order schema. Their own example is a Slack `text` field or a plain sentence.

Pros of treating the alert as text: it matches the document, and a field named like a price cannot become a fill. Cons: a later ingester still has to learn whatever JSON the chart author typed, and TradingView will cancel the POST after 3 seconds.

There was no alert ingester in this repo. There still is no HTTP endpoint for one. `validate_tradingview` stores a message in memory, sets `interpreted_as_order` false, and leaves `quote` null. Recording defaults off. The function has no HTTP client, so it cannot reach a broker. A copied TradersPost-shaped object passed to this recorder is still stored as a message, not forwarded.

Flow if you later connect the vendors yourself, outside this process:

1. You write the alert message in TradingView and set a webhook URL.
2. TradingView POSTs that message from the IP list in their help page.
3. If the URL is a TradersPost or SignalStack webhook, that vendor can turn the JSON into a broker order. That hop is their product, not this API.
4. The Veytrix chart never sees that POST. It keeps plotting API bars.

## TradersPost

Official integration path: a JSON POST to `https://webhooks.traderspost.io/trading/webhook/{uuid}/{password}`. Required fields are `ticker` and `action` (`buy`, `sell`, `add`, `resize`, `exit`, `reverse`, `breakeven`, `cancel`). The FAQ points at webhooks rather than a separate REST trading API for this job. The webhook reference also documents a 16,384-byte budget, nesting and formula limits, and HTTP 413 with no signal log when the budget is exceeded. Batch arrays are off unless the strategy allows them. This recorder leaves batches off and saves no row when the local budget fails.

Pros: the payload shape is published and can be checked without an account. Cons: their success response means they accepted a signal that can become a broker order. Calling that URL from Veytrix would be an order path. This code does not call it.

`validate_traderspost` checks the documented fields, including `resize` without `quantity`. Formulas that start with `=` are counted and not evaluated. A valid payload while recording is off returns `route-disabled`. With recording on and the route selected, the row is still `broker-forwarding-disabled`. `broker_outcome` stays `rejected`. `forwarded` stays false.

## SignalStack

SignalStack's help centre documents webhooks created in the product under Brokers & Webhooks. A production webhook can turn a signal into a broker order. A test webhook checks that a payload arrives. The Alpaca stock page shows JSON with `symbol`, `action` (`buy`, `sell`, `close`), optional `quantity`, `quantity_type` (`fixed`, `cash`, `percent_of_equity`), `limit_price`, and `stop_price`. The page says an omitted quantity is calculated or defaulted to 1. This recorder does not do that: `quantity_omitted` stays true and `quantity_defaulted` stays false.

The Interactive Brokers page also mentions `cancel` and `exit`. The Alpaca stock page does not. The adapter follows the Alpaca page.

No public REST trading API, OpenAPI file, or stable webhook host was found that could be called without an account-generated URL. None is called.

Pros: the Alpaca examples are specific enough to validate. Cons: the help pages are broker-specific and are not a machine-readable schema, so a future field can drift. Confidence in the field list is high for the page fetched on 13 November 2026 and medium after that.

The same rejection, dedupe, retry, and timeout behaviour applies. The local timeout budget is 3 seconds, matching TradingView's cancel window. SignalStack's page does not publish that number. It is a local budget, not a claim about their servers.

## One route

`PaperBoundary.select` keeps one route for a strategy id and one route for an account label. The default is `none`. Choosing SignalStack while TradersPost is already selected on that strategy or that label raises `RouteConflict`. `replace=True` switches the same pair only. The account label is a short local name such as `paper-a`. It is not an Alpaca account number and it is not checked with Alpaca.

Recording is a second switch and defaults off. `enable_recording` refuses when `VEYTRIX_ENABLE_LIVE_BROKER`, `ALPACA_LIVE_TRADE`, or `MAC01_LIVE_CONFIRM` is set to a value other than empty, `0`, `false`, `no`, or `off`. The boundary stores the variable names, not the values.

Audit rows are process-local. They are not the API `audit_events` table and they are not broker fills. The log line is `mode=paper` and does not print the sender body, so a number in the payload is not logged as a quote.

Pros of an in-memory log: no migration and no way for the API to treat the row as an order. Cons: the rows disappear when the process exits. That is the safe default until a reviewed store exists.

## Market Gear

Market Gear's Alpaca page describes a charting, options, and journal product that connects to an Alpaca account, and says you can use virtual accounts to practise without risk. The company is iVest Plus, Inc. The same site's older broker table and the Google Play listing name TD Ameritrade, E*TRADE, Ally, and ChoiceTrade, not a developer API.

No Market Gear developer documentation, webhook schema, or order API was found. This slice does not invent one and does not route orders to Market Gear.

Pros of leaving it as a manual product: the user-facing page is enough to explain the connection, and there is no fake client to grow into a live adapter. Cons: the virtual-account click path is not specified beyond "use your Virtual accounts", so this note cannot tell you which button to press. Confidence is high that no developer API was published on the pages searched, and medium on the exact virtual-account steps.

Manual, if you choose to use it:

1. Create the Market Gear account yourself at their site.
2. Connect Alpaca in their UI. Do not paste the keys into this repo or into chat.
3. Use the virtual account they offer when you want practice. Keep that separate from any live Alpaca account.
4. Do not point a TradingView or SignalStack webhook at the same Alpaca account that another route already uses.

## Alpaca CLI

Alpaca's CLI document (alpha preview) says paper trading is the default. Live trading needs `alpaca profile login --api-key --live` or `ALPACA_LIVE_TRADE=true`. Install is `brew install alpacahq/tap/cli` or `go install github.com/alpacahq/cli/cmd/alpaca@latest`, then `alpaca version` and `alpaca doctor`. Credentials land in `~/.config/alpaca/profiles/` with mode `0600`. OAuth paper login is `alpaca profile login` and opens a browser.

The same document says the CLI has no confirmation prompts and is meant to be usable by an agent. This repository does not follow that part. No web route and no assistant shells out to `alpaca`. `review_command` only classifies an argv list. `executed` is always false. Live flags, mutating commands (`order submit` without `--dry-run`, cancels, position closes, raw `api POST`), and shell syntax fail the check.

Paper checklist examples, not executed here:

```text
alpaca version
alpaca doctor
alpaca profile list
alpaca account get
alpaca order list
alpaca clock
alpaca order submit --symbol AAPL --side buy --qty 1 --type market --dry-run
```

Manual, if you want the CLI on this machine:

1. Install it yourself. This pass did not.
2. Use paper login. Do not set `ALPACA_LIVE_TRADE=true`.
3. Regenerate any Alpaca key that has been pasted into a chat before you use it.
4. Keep paper and live profiles separate. Do not pass a live profile to a command the checklist would reject.

## Public assistants

These do not belong in the trading API. The API has no auth gateway, and a public user would turn the desk into a multi-user trading product. The assistants are separate directories. They do not import `veytrix_quant`, `veytrix_api`, the broker adapters, or the private tables. They have no brokerage credentials and no order tools.

Pros of separate apps: a bug in note search or a model call cannot reach `Mac01Engine.run`. Cons: there is no shared login, and the Grok limits are in-process rather than a hosted account system. That is acceptable because neither app is exposed as a public server in this slice.

### Obsidian

Built from the plugin guide and the `Vault` API. `apps/obsidian-assistant` pins notes, reads those paths with `Vault.read`, and answers with excerpts that are slices of the note text plus the note path. Create uses `Vault.create`, edit uses `Vault.modify`, and delete uses `Vault.trash` after a confirm dialog. `applyMutation` returns `confirmation_required` when the confirmation is missing, declined, or for a different action. `READS_WHOLE_VAULT`, `EXPOSES_PUBLIC_ENDPOINT`, and `UPLOADS_VAULT` are false.

Pros: consent is a pure function and can be tested without Obsidian. Cons: `src/main.ts` is not bundled to `main.js` here, so Obsidian will not load the folder until you compile it in a throwaway vault. The guide says not to develop a plugin in your main vault.

### Grok

xAI's current recommendation for new integrations is the Responses API, `POST https://api.x.ai/v1/responses`. Chat completions are documented as legacy. The example model name on the responses page fetched for this slice is `grok-4.7`. Provider storage defaults to keeping a response for 30 days. `build_responses_body` always sends `store: false`.

`GrokAssistant` reports `unconfigured` when no key is set. `api_key_from_env` reads `XAI_API_KEY` from a mapping and has no file loader. The default transport raises `OfflineError`. Tests inject a fake transport and patch `socket.socket`. Bearer credentials map to a tenant and a user. The limiter key is that pair, so one tenant cannot spend another's budget. Usage rows store status and unit counts, not the prompt or the answer, and `purge` drops rows older than the retention window.

Pros: the controls can be proven without an xAI account. Cons: there is no HTTP server in front of the class, and a real call is a later change. Do not create an xAI account as part of this work. Do not commit a key.

## What this slice refuses

- No `VEYTRIX_ENABLE_LIVE_BROKER`, `ALPACA_LIVE_TRADE=true`, or `MAC01_LIVE_CONFIRM` was set.
- No order route was added. The risk-size response flags stay false.
- No webhook, chart, model reply, or signal can call MAC-01, alpaca-py, or the Alpaca CLI.
- TradersPost and SignalStack are not connected to the same strategy or account label.
- No prices or fills were invented. Sender JSON is stored as sender JSON. `quote` is null.
- No third-party account was created and no credential was entered.

## References

Alpaca. (n.d.). *Trading CLI*. https://docs.alpaca.markets/us/docs/alpacas-cli

Market Gear. (n.d.). *Market Gear for Alpaca*. https://www.marketgear.com/alpaca/

Obsidian. (n.d.). *Build a plugin*. https://docs.obsidian.md/Plugins/Getting%20started/Build%20a%20plugin

Obsidian. (n.d.). *Vault*. https://docs.obsidian.md/Reference/TypeScript+API/Vault

SignalStack. (n.d.). *Create webhooks*. https://help.signalstack.com/kb/getting-started/create-webhooks

SignalStack. (n.d.). *Stocks | Alpaca*. https://help.signalstack.com/kb/alpaca/alpaca-stock

TradersPost. (n.d.). *Signal message reference*. https://docs.traderspost.io/docs/core-concepts/webhooks

TradersPost. (n.d.). *Webhook reference*. https://docs.traderspost.io/docs/developer-resources/webhook-reference

TradingView. (n.d.). *How to configure webhook alerts*. https://www.tradingview.com/support/solutions/43000529348-about-webhooks/

xAI. (2026, October 10). *Comparison with Chat Completions*. https://docs.x.ai/developers/model-capabilities/text/comparison

xAI. (2026, October 20). *Responses*. https://docs.x.ai/developers/rest-api-reference/inference/responses
