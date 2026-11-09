# AI research

Research notes are rows in the local API database. No model provider is configured in this sprint.

A research assistant must not receive production broker credentials and must not have a tool that can place, modify, or cancel an order, sign a wallet transaction, or move money. Model output and fetched web content stay on the research side of the execution boundary.

## Simulated paper swaps (`veytrix_ai`)

This package holds a paper-swap CLI. It records a simulated fill. It does not sign, broadcast, or read a private key. It is not an agent tool. No model, prompt, or API route can call it. A swap is recorded only when you type a CLI command.

What it enforces:

- **Testnets only.** Solana devnet, Ethereum Sepolia (`11155111`), and Base Sepolia (`84532`). Mainnet chain ids and the mainnet RPC URLs in `swapbot.yaml` are refused. There is no override.
- **No key material.** A config field or environment variable holding a private key, mnemonic, or seed phrase is refused. Nothing in this package imports a signing library.
- **Read-only prices.** On Sepolia and Base Sepolia the CLI calls Uniswap QuoterV2 `quoteExactInputSingle` with `eth_call`, then `eth_gasPrice`. It does not send a transaction. On Solana, `https://quote-api.jup.ag` prices mainnet mints and this build did not find a devnet quote on that host, so the CLI uses Coinbase's public SOL-USD spot (`https://api.coinbase.com/v2/prices/SOL-USD/spot`) and labels it `coinbase-sol-usd-reference`. Every receipt has `simulated: true`.
- **Simulated accounting.** `max_slippage_bps` (default 50, ceiling 500) is applied with `Decimal`. The estimated fee is deducted from the native balance. Starting balances are in the config (1 ETH, 100 SOL, and 1000 USDC on each chain). An insufficient balance is refused. Fills and balances are stored in Postgres. The tables hold no keys.
- The kill switch `var/swapbot.KILL` is checked before a quote or a swap.
- The API exposes `GET /api/v1/paper-swaps/portfolio` and `GET /api/v1/paper-swaps/orders` only. It does not submit a swap.

## Use

Install the repo (`pip install -e ".[dev]"`) so the CLI can import the API models. Export testnet RPC URLs in the shell. Do not put a private key in the environment.

```text
ETHEREUM_SEPOLIA_RPC_URL=   # any Sepolia endpoint; eth_chainId must be 11155111
BASE_SEPOLIA_RPC_URL=https://sepolia.base.org
SOLANA_DEVNET_RPC_URL=https://api.devnet.solana.com
```

Apply the local migration first (`alembic -c services/api/alembic.ini upgrade head` with `VEYTRIX_ENV=local`).

```bash
python -m veytrix_ai.swapbot status
python -m veytrix_ai.swapbot quote --chain ethereum ETH USDC 0.01
python -m veytrix_ai.swapbot swap --chain ethereum ETH USDC 0.01
python -m veytrix_ai.swapbot portfolio
python -m veytrix_ai.swapbot kill --reason "stop"
python -m veytrix_ai.swapbot resume
```

`quote` prints a simulated price and writes nothing. `swap` records a simulated fill. There is no `--broadcast` flag.

The Solidity helpers in `contracts/` are unaudited reference code. This CLI does not deploy them.

## References

Base. (n.d.). *Connect to Base*. https://docs.base.org/get-started/connect-to-base

Circle. (n.d.). *USDC contract addresses*. https://developers.circle.com/stablecoins/usdc-contract-addresses

Solana. (n.d.). *Clusters*. https://solana.com/docs/references/clusters

Uniswap Labs. (n.d.). *Base deployments*. https://docs.uniswap.org/contracts/v3/reference/deployments/base-deployments

Uniswap Labs. (n.d.). *Ethereum deployments*. https://docs.uniswap.org/contracts/v3/reference/deployments/ethereum-deployments
