# Alpaca CLI

Alpaca documents the CLI as an operator terminal tool. Paper trading is the default profile. Live trading is a separate configuration and is not used here.

https://docs.alpaca.markets/us/docs/alpacas-cli

Install and sign in from Alpaca's own instructions, on your machine, in a terminal you run yourself. Do not set `ALPACA_LIVE_TRADE=true`. Do not put live keys in this repository.

Veytrix does not invoke the CLI. No web route and no agent tool runs a shell command or submits an order through it. MAC-01 remains the only order path, and it stays behind its existing gate. This build does not call it with `--submit`.
