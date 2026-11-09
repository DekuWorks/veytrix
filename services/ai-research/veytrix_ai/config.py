"""Load and validate services/ai-research/swapbot.yaml. Fails closed.

The file names RPC environment variables. It does not contain a private key,
and the mainnet URL on each chain is a value this build refuses to request.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import yaml

from veytrix_ai.abi import UINT24_MAX, AbiError, require_checksummed

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = REPO_ROOT / "services" / "ai-research" / "swapbot.yaml"
DEFAULT_STATE_DIR = REPO_ROOT / "var"

MAX_SLIPPAGE_BPS_CEILING = 500
REQUIRED_CHAINS = frozenset({"solana", "ethereum", "base"})

# Published deployments. A config that disagrees is refused.
# Uniswap QuoterV2 / WETH: docs.uniswap.org ethereum-deployments and base-deployments.
# USDC: developers.circle.com/stablecoins/usdc-contract-addresses.
# Wrapped SOL mint is the canonical SPL mint used to identify native SOL.
KNOWN_QUOTER = {
    "11155111": "0xEd1f6473345F45b75F8179591dd5bA1888cf2FB3",
    "84532": "0xC5290058841028F1614F3A6F0F5816cAd0df5E27",
}
KNOWN_WETH = {
    "11155111": "0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14",
    "84532": "0x4200000000000000000000000000000000000006",
}
KNOWN_USDC = {
    "11155111": "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238",
    "84532": "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
    "devnet": "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU",
}
KNOWN_SOL_MINT = "So11111111111111111111111111111111111111112"

ALLOWED = {
    "solana": {
        "kind": "solana",
        "network": "solana-devnet",
        "chain_id": "devnet",
        "rpc_env_var": "SOLANA_DEVNET_RPC_URL",
        "mainnet_chain_id": "mainnet-beta",
        "mainnet_rpc_url": "https://api.mainnet.solana.com",
        "native_symbol": "SOL",
    },
    "ethereum": {
        "kind": "evm",
        "network": "sepolia",
        "chain_id": "11155111",
        "rpc_env_var": "ETHEREUM_SEPOLIA_RPC_URL",
        "mainnet_chain_id": "1",
        "mainnet_rpc_url": "https://cloudflare-eth.com",
        "native_symbol": "ETH",
    },
    "base": {
        "kind": "evm",
        "network": "base-sepolia",
        "chain_id": "84532",
        "rpc_env_var": "BASE_SEPOLIA_RPC_URL",
        "mainnet_chain_id": "8453",
        "mainnet_rpc_url": "https://mainnet.base.org",
        "native_symbol": "ETH",
    },
}

MAINNET_CHAIN_IDS = frozenset({"1", "8453", "mainnet-beta", "mainnet"})
REFUSED_HOSTS = frozenset(
    {
        "mainnet.base.org",
        "mainnet-sequencer.base.org",
        "api.mainnet.solana.com",
        "cloudflare-eth.com",
    }
)

TOP_KEYS = frozenset({"max_slippage_bps", "chains"})
CHAIN_KEYS = frozenset(
    {
        "kind",
        "network",
        "chain_id",
        "rpc_env_var",
        "mainnet_rpc_url",
        "mainnet_chain_id",
        "native_symbol",
        "quoter",
        "weth_symbol",
        "fee_tier",
        "fallback_gas_units",
        "fee_estimate_native",
        "reference_pair",
        "starting_balances",
        "tokens",
    }
)
FORBIDDEN_KEYS = frozenset(
    {
        "private_key",
        "secret",
        "mnemonic",
        "seed",
        "wallet",
        "broadcast",
        "helper_contract",
        "signer",
    }
)

_SYMBOL = re.compile(r"^[A-Z0-9]{1,11}$")
_BASE58 = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Token:
    symbol: str
    address: str
    decimals: int


@dataclass(frozen=True)
class ChainConfig:
    name: str
    kind: str
    network: str
    chain_id: str
    rpc_env_var: str
    mainnet_rpc_url: str
    mainnet_chain_id: str
    native_symbol: str
    native_decimals: int
    tokens: dict[str, Token]
    starting_balances: dict[str, Decimal]
    quoter: str | None = None
    weth_symbol: str | None = None
    fee_tier: int | None = None
    fallback_gas_units: int | None = None
    fee_estimate_native: Decimal | None = None
    reference_pair: str | None = None

    def tradeable_symbols(self) -> list[str]:
        symbols = list(self.tokens)
        if self.native_symbol not in symbols:
            symbols.insert(0, self.native_symbol)
        return symbols


@dataclass(frozen=True)
class SwapbotConfig:
    max_slippage_bps: int
    chains: dict[str, ChainConfig]


def _reject_key_material(data: Any) -> None:
    if isinstance(data, dict):
        for key, value in data.items():
            lowered = str(key).lower().replace("-", "_")
            if lowered in FORBIDDEN_KEYS or "private" in lowered or "mnemonic" in lowered:
                raise ConfigError("config must not contain key material")
            _reject_key_material(value)
    elif isinstance(data, list):
        for item in data:
            _reject_key_material(item)


def _text_id(raw: Any, name: str) -> str:
    if isinstance(raw, bool) or not isinstance(raw, str | int):
        raise ConfigError(f"{name} must be a string or integer")
    return str(raw)


def _int(raw: Any, name: str, low: int, high: int) -> int:
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise ConfigError(f"{name} must be an integer")
    if not low <= raw <= high:
        raise ConfigError(f"{name} must be between {low} and {high}")
    return raw


def _amount(raw: Any, name: str) -> Decimal:
    if isinstance(raw, bool) or not isinstance(raw, str | int):
        raise ConfigError(f"{name} must be a quoted decimal string or an integer")
    try:
        value = Decimal(str(raw))
    except InvalidOperation:
        raise ConfigError(f"{name} is not a decimal") from None
    if not value.is_finite() or value <= 0:
        raise ConfigError(f"{name} must be a positive decimal")
    return value


def _evm_address(raw: Any, name: str) -> str:
    try:
        return require_checksummed(raw, name)
    except AbiError as exc:
        raise ConfigError(str(exc)) from None


def _parse_tokens(raw: Any, chain_name: str, chain_id: str, kind: str) -> dict[str, Token]:
    if not isinstance(raw, dict) or not raw:
        raise ConfigError(f"{chain_name}.tokens must be a non-empty allowlist")
    tokens: dict[str, Token] = {}
    for symbol, spec in raw.items():
        if not isinstance(symbol, str) or not _SYMBOL.match(symbol):
            raise ConfigError(f"invalid token symbol: {symbol!r}")
        if not isinstance(spec, dict):
            raise ConfigError(f"{chain_name}.tokens.{symbol} must have address and decimals")
        extra = set(spec) - {"address", "decimals"}
        if extra:
            raise ConfigError(f"unknown token keys: {', '.join(sorted(extra))}")
        address = spec.get("address")
        if kind == "evm":
            address = _evm_address(address, f"{chain_name}.tokens.{symbol}.address")
        elif not isinstance(address, str) or not _BASE58.match(address):
            raise ConfigError(f"{chain_name}.tokens.{symbol}.address is not a Solana address")
        decimals = _int(spec.get("decimals"), f"{chain_name}.tokens.{symbol}.decimals", 0, 18)
        tokens[symbol] = Token(symbol, address, decimals)
    if kind == "evm":
        weth = KNOWN_WETH[chain_id]
        usdc = KNOWN_USDC[chain_id]
        if set(tokens) != {"WETH", "USDC"}:
            raise ConfigError(f"{chain_name} allowlist must be WETH and USDC")
        if tokens["WETH"].address != weth or tokens["WETH"].decimals != 18:
            raise ConfigError(f"{chain_name} WETH does not match the published address")
        if tokens["USDC"].address != usdc or tokens["USDC"].decimals != 6:
            raise ConfigError(f"{chain_name} USDC does not match the published address")
    else:
        usdc = KNOWN_USDC[chain_id]
        if set(tokens) != {"SOL", "USDC"}:
            raise ConfigError("solana allowlist must be SOL and USDC")
        if tokens["SOL"].address != KNOWN_SOL_MINT or tokens["SOL"].decimals != 9:
            raise ConfigError("solana SOL mint does not match the published wrapped SOL mint")
        if tokens["USDC"].address != usdc or tokens["USDC"].decimals != 6:
            raise ConfigError("solana USDC does not match the published address")
    return tokens


def _parse_chain(name: str, raw: Any) -> ChainConfig:
    expected = ALLOWED.get(name)
    if expected is None:
        raise ConfigError(f"unknown chain {name}")
    if not isinstance(raw, dict):
        raise ConfigError(f"{name} must be a mapping")
    unknown = set(raw) - CHAIN_KEYS
    if unknown:
        raise ConfigError(f"unknown config keys: {', '.join(sorted(map(str, unknown)))}")
    chain_id = _text_id(raw.get("chain_id"), f"{name}.chain_id")
    if chain_id in MAINNET_CHAIN_IDS or chain_id != expected["chain_id"]:
        raise ConfigError(f"chain {chain_id} is not an allowed testnet; this build is testnet only")
    identity = (
        "kind",
        "network",
        "rpc_env_var",
        "mainnet_rpc_url",
        "mainnet_chain_id",
        "native_symbol",
    )
    for field in identity:
        actual = raw.get(field)
        if field == "mainnet_chain_id":
            actual = _text_id(actual, f"{name}.{field}")
        if actual != expected[field]:
            raise ConfigError(f"{name}.{field} does not match the allowed testnet")
    mainnet_chain = _text_id(raw.get("mainnet_chain_id"), f"{name}.mainnet_chain_id")
    if mainnet_chain not in MAINNET_CHAIN_IDS:
        raise ConfigError(f"{name}.mainnet_chain_id must be a refused mainnet id")
    tokens = _parse_tokens(raw.get("tokens"), name, chain_id, expected["kind"])
    tradeable = [expected["native_symbol"], *tokens]
    balances_raw = raw.get("starting_balances")
    if not isinstance(balances_raw, dict) or not balances_raw:
        raise ConfigError(f"{name}.starting_balances must map symbols to amounts")
    balances = {
        symbol: _amount(value, f"{name}.starting_balances.{symbol}")
        for symbol, value in balances_raw.items()
    }
    for symbol in balances:
        if symbol not in tradeable:
            raise ConfigError(f"{name}.starting_balances.{symbol} is not an allowlisted token")
    if expected["kind"] == "evm":
        quoter = _evm_address(raw.get("quoter"), f"{name}.quoter")
        if quoter != KNOWN_QUOTER[chain_id]:
            raise ConfigError(f"{name}.quoter does not match Uniswap's published QuoterV2")
        if raw.get("weth_symbol") != "WETH":
            raise ConfigError(f"{name}.weth_symbol must be WETH")
        fee_tier = _int(raw.get("fee_tier"), f"{name}.fee_tier", 1, min(UINT24_MAX, 999_999))
        if fee_tier != 3000:
            raise ConfigError(f"{name}.fee_tier must be 3000")
        fallback = _int(
            raw.get("fallback_gas_units"), f"{name}.fallback_gas_units", 21_000, 1_000_000
        )
        if raw.get("fee_estimate_native") is not None or raw.get("reference_pair") is not None:
            raise ConfigError(f"{name} is an EVM chain and has no reference-price fields")
        return ChainConfig(
            name=name,
            kind="evm",
            network=expected["network"],
            chain_id=chain_id,
            rpc_env_var=expected["rpc_env_var"],
            mainnet_rpc_url=expected["mainnet_rpc_url"],
            mainnet_chain_id=mainnet_chain,
            native_symbol=expected["native_symbol"],
            native_decimals=tokens["WETH"].decimals,
            tokens=tokens,
            starting_balances=balances,
            quoter=quoter,
            weth_symbol="WETH",
            fee_tier=fee_tier,
            fallback_gas_units=fallback,
        )
    fee = _amount(raw.get("fee_estimate_native"), f"{name}.fee_estimate_native")
    if raw.get("reference_pair") != "SOL-USD":
        raise ConfigError("solana.reference_pair must be SOL-USD")
    if raw.get("quoter") or raw.get("weth_symbol") or raw.get("fee_tier"):
        raise ConfigError("solana has no QuoterV2 deployment in this build")
    return ChainConfig(
        name=name,
        kind="solana",
        network=expected["network"],
        chain_id=chain_id,
        rpc_env_var=expected["rpc_env_var"],
        mainnet_rpc_url=expected["mainnet_rpc_url"],
        mainnet_chain_id=mainnet_chain,
        native_symbol="SOL",
        native_decimals=tokens["SOL"].decimals,
        tokens=tokens,
        starting_balances=balances,
        fee_estimate_native=fee,
        reference_pair="SOL-USD",
    )


def parse_config(data: Any) -> SwapbotConfig:
    _reject_key_material(data)
    if not isinstance(data, dict):
        raise ConfigError("config must be a mapping")
    unknown = set(data) - TOP_KEYS
    if unknown:
        raise ConfigError(f"unknown config keys: {', '.join(sorted(map(str, unknown)))}")
    raw_chains = data.get("chains")
    if not isinstance(raw_chains, dict) or set(raw_chains) != REQUIRED_CHAINS:
        raise ConfigError("config must list solana, ethereum, and base, and no other chain")
    chains = {name: _parse_chain(name, raw) for name, raw in raw_chains.items()}
    return SwapbotConfig(
        max_slippage_bps=_int(
            data.get("max_slippage_bps", 50), "max_slippage_bps", 1, MAX_SLIPPAGE_BPS_CEILING
        ),
        chains=chains,
    )


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> SwapbotConfig:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        raise ConfigError(f"cannot read config at {path}") from None
    return parse_config(yaml.safe_load(text))
