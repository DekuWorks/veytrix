# Execution

This directory is still a placeholder. It contains no adapter, gateway, or router.

The only broker adapter in the repository is the MAC-01 command-line bot in `services/quant/veytrix_quant/mac01`. It uses the Alpaca Trading API, paper by default. It can submit only from `python -m veytrix_quant.mac01 run --submit` or `schedule --submit`. Live submission stays behind the eight-condition gate in `services/quant/README.md`. No live order has been placed, and no paper order has been placed from this tree. There is no `.env` here. A key pair pasted into a chat earlier is compromised and must be regenerated before any Alpaca call.

Simulated testnet swaps live in `services/ai-research/veytrix_ai`. They do not sign or broadcast. The API can read them and cannot submit one.

Do not add a second broker client in this directory, and do not wrap a live SDK behind a flag on the API. The API still refuses to boot if `VEYTRIX_ENABLE_LIVE_BROKER` is set.

Shorting, leverage, derivatives execution, NFT wallet signing, and bank transfers are out of scope.
