# Cursor subscription and Veytrix runtime

Checked against Cursor's public pricing pages on 9 November 2026. This session cannot see the owner's plan, remaining usage, or reset date. Those figures are in the editor's settings and at the billing dashboard. Nothing here reads Cursor session credentials.

Sources:

- [Models and pricing](https://cursor.com/docs/models-and-pricing)
- [Pricing and plans](https://cursor.com/help/account-and-billing/pricing.md)
- [Legacy Cursor plans](https://cursor.com/docs/account/pricing/legacy-cursor-plans)

## What included usage can cover

Cursor usage pays for coding inside Cursor: editor agent, CLI, and, on plans that include them, Cloud Agents and Automations. That is development of this repository. It does not start the MAC-01 runner, the swap bot, or the nine desk names.

Paid plans include a pool for Cursor's own models (Grok 4.7, Grok 4.6, Grok 4.5, and Composer 2.5). On The X Subscription that pool resets weekly. Legacy Pro, Pro+, and Ultra plans use two monthly pools instead. Third-party models (Claude, GPT, Gemini) are billed separately: from prepaid credit on Premium and above, or from the legacy "Other Models" pool and on-demand usage. The Grok API is billed separately and does not draw from the included pool.

Plus does not include Cloud Agents, Automations, Origin, or third-party models. Premium and above do. This checkout already uses a private Origin repository (`dekuworks/veytrix`). Origin being present does not prove the plan tier, because the account may be on a legacy plan.

## What this build does not do

- It does not call Cursor, Grok, OpenAI, Anthropic, or Google at runtime.
- It does not buy credits or change the subscription.
- It does not treat the nine names (Roads, Dayvid, Nyx, Astra, Lyra, Vex, Cipher, Aegis, Midas) as deployed processes. They are labels on the existing disabled desks.
- `GET /api/v1/inference/posture` reports `cursor_subscription_runs_agents: false`.

## Local routing

`VEYTRIX_PAID_INFERENCE` defaults off. `VEYTRIX_AI_MONTHLY_CEILING_USD` defaults to 0. A paid provider is paused in both cases. Setting both still does not call a provider, because no paid client is configured. `VEYTRIX_OLLAMA_URL` opts into a local model label only. This API does not send the request.

Deterministic tasks (`position_size`, `sma_crossover`, `treasury_split`, `reconcile`, `risk_check`) stay on the existing Python code and use no model.

## Deployment report

1. **Cursor features used.** Editor agents wrote and reviewed this repository. Origin hosts the private remote `dekuworks/veytrix`, which is still empty because a normal push was refused. 21st.dev theme lookup was used for the dashboard. Cloud Agents, Automations, and the Cloud Agents API were not configured.
2. **Included usage.** Coding in this editor draws from the Cursor model pool on whatever plan the account is on. The plan name, remaining balance, and reset date were not read.
3. **Separately billed.** Third-party models in Cursor, the Grok API, a new Supabase project (about $10 a month, and blocked by overdue DekuWorks invoices), and any future paid model key. None of those were purchased here.
4. **Estimated operating cost of this runtime.** $0. The API does not call a model. MAC-01 and the swap bot are not left running. Alpaca paper keys are still absent.
5. **Health.** `GET /api/v1/inference/posture` reports the nine names, paid inference off, ceiling $0, and `cursor_subscription_runs_agents: false`. The ten desks stay disabled. No persona process was started.
6. **Blockers.** Owner must confirm the Cursor plan in settings. Alpaca paper keys and a written yes are required before any paper order. Supabase invoices must be settled before a project can be created. Ollama is not configured. There is no auth, no WhatsApp, no Mission Control deploy, and no persistent host for the nine names. Live trading stays behind the unused MAC-01 gate.
