# Execution

Paper recorders live in `veytrix_execution`. Recording is off and the selected route is `none` until an operator changes that in memory. A selected route still returns `broker_outcome=rejected`. There is no HTTP client, no broker client, and no order route.

The API process does not import this package. Do not add one. Do not add a second broker client here, and do not wrap a live SDK behind a flag on the API. The API still refuses to boot if `VEYTRIX_ENABLE_LIVE_BROKER` is set.

The only broker adapter in the repository is the MAC-01 command-line bot in `services/quant/veytrix_quant/mac01`. It uses the Alpaca Trading API, paper by default. It can submit only from `python -m veytrix_quant.mac01 run --submit` or `schedule --submit`. Live submission stays behind the eight-condition gate in `services/quant/README.md`. No live order has been placed, and no paper order has been placed from this tree. There is no `.env` here. A key pair pasted into a chat earlier is compromised and must be regenerated before any Alpaca call.

`cli_guard.py` is a checklist for commands an operator might type in a terminal. It does not start a process. Live flags fail the check.

Simulated testnet swaps live in `services/ai-research/veytrix_ai`. They do not sign or broadcast. The API can read them and cannot submit one.

Shorting, leverage, derivatives execution, NFT wallet signing, and bank transfers are out of scope.

The architecture notes for TradingView, TradersPost, SignalStack, Market Gear, and the Alpaca CLI are in `docs/TRADING_TOOLS_PLAN.md`.
