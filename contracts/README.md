# Contracts

Uniswap V3 swap helpers. **Unaudited. Not deployed.** The paper-swap CLI no longer signs or deploys these contracts; they are reference only.

| File | Router it targets | Where that router exists |
| --- | --- | --- |
| `src/MultiHopSwap.sol` | Original `SwapRouter` (`deadline` inside the structs) | Ethereum mainnet, Arbitrum, Optimism, Polygon. Not Sepolia. |
| `src/MultiHopSwap02.sol` | `SwapRouter02` / `IV3SwapRouter` (no `deadline` field) | Sepolia and most newer chains |

The two files have the same logic and checks. Only the router struct layout differs, and the 02 variant relies on its own `deadline < block.timestamp` check because the router no longer takes one. Calling the wrong variant against a router reverts, because the function selectors differ.

Both helpers:

- have no owner, admin, pause, or rescue function
- pay output to `msg.sender` only (no recipient argument)
- approve the router for exactly `amountIn` and reset the allowance to 0 afterwards
- refuse ETH from anyone except WETH
- do **not** support fee-on-transfer or rebasing tokens

## Setup

Foundry is not installed on this machine yet, so nothing here has been compiled or run.

```bash
curl -L https://foundry.paradigm.xyz | bash
foundryup
cd contracts
forge install foundry-rs/forge-std OpenZeppelin/openzeppelin-contracts@v5.1.0 --no-git
forge build
forge test
```

`lib/`, `out/`, `cache/`, and `broadcast/` are gitignored.

Fork tests skip unless an RPC URL is set. They run in a local fork and send nothing:

```bash
SEPOLIA_RPC_URL="https://..." forge test --match-contract Fork -vv
```

Never commit an RPC URL. Provider URLs usually embed an API key.

## Deploy

Not used by this build. The paper-swap CLI does not deploy these contracts and does not take a private key. The Foundry script remains in the tree as reference code and still refuses any chain except Sepolia.

## Addresses

Checked on 8 November 2026:

- Sepolia SwapRouter02 `0x3bFA4769FB09eefC5a80d6E87c3B9C650f7Ae48E`, QuoterV2 `0xEd1f6473345F45b75F8179591dd5bA1888cf2FB3`, WETH `0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14` (Uniswap Labs, n.d.)
- Sepolia USDC `0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238` (Circle, n.d.)

## Before any mainnet use

An independent audit and fork tests against the real router. This build is testnet only. See `docs/reviews/PENDING.md`.

## References

Circle. (n.d.). *USDC contract addresses*. https://developers.circle.com/stablecoins/usdc-contract-addresses

Uniswap Labs. (n.d.). *Ethereum deployments*. https://docs.uniswap.org/contracts/v3/reference/deployments/ethereum-deployments
