"""Read-only prices. eth_call and one public spot URL. No send methods."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal, InvalidOperation
from typing import Any
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from veytrix_ai.abi import AbiError, decode_uint, encode_quote_single
from veytrix_ai.config import REFUSED_HOSTS, ChainConfig, SwapbotConfig
from veytrix_ai.guards import (
    GuardError,
    from_base_units,
    native_fee,
    to_base_units,
)

# quote-api.jup.ag prices Solana mainnet. This build did not find a devnet
# quote route on that host, so Solana uses Coinbase's public SOL-USD spot
# and labels the result as a reference price.
COINBASE_SOL_USD_SPOT = "https://api.coinbase.com/v2/prices/SOL-USD/spot"
QUOTE_SOURCE_POOL = "uniswap-v3-quoterv2-eth_call"
QUOTE_SOURCE_REFERENCE = "coinbase-sol-usd-reference"

# Stable cluster genesis hashes. https://solana.com/docs/references/clusters lists the
# public RPC endpoints but not these hashes. Mainnet-beta is refused. Only the
# devnet hash is accepted, so a mainnet endpoint cannot be used by mistake.
SOLANA_DEVNET_GENESIS = "EtWTRABZaYq6iMfeYKouRu166VU2xqa1wcaWoxPkrZBG"
SOLANA_MAINNET_GENESIS = "5eykt4UsFv8P8NJdTREpY1vzqKqZKvdpKuc147dw2N9d"

ALLOWED_RPC_METHODS = frozenset({"eth_chainId", "eth_call", "eth_gasPrice", "getGenesisHash"})


class QuoteError(GuardError):
    pass


@dataclass(frozen=True)
class RawQuote:
    quoted_out: Decimal
    fee_estimate: Decimal
    fee_symbol: str
    quote_source: str
    price_kind: str


def _host(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise GuardError("RPC URL is not an HTTP URL")
    return parsed.hostname.lower()


def assert_rpc_url_allowed(url: str, mainnet_rpc_url: str) -> None:
    host = _host(url)
    if host in REFUSED_HOSTS or "mainnet" in host or url.rstrip("/") == mainnet_rpc_url.rstrip("/"):
        raise GuardError("mainnet RPC URL is refused")


def _hex_int(value: Any, label: str) -> int:
    if not isinstance(value, str) or not value.startswith("0x"):
        raise QuoteError(f"{label} was not hex")
    try:
        return int(value, 16)
    except ValueError:
        raise QuoteError(f"{label} was not hex") from None


def _post_json(url: str, payload: dict[str, Any], timeout: float = 10) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except (URLError, TimeoutError, OSError):
        raise QuoteError("market data request failed") from None
    return _decode_json(raw)


def _get_json(url: str, timeout: float = 10) -> dict[str, Any]:
    request = Request(url, headers={"Accept": "application/json"}, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except (URLError, TimeoutError, OSError):
        raise QuoteError("market data request failed") from None
    return _decode_json(raw)


def _decode_json(raw: bytes) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        raise QuoteError("market data response was not JSON") from None
    if not isinstance(parsed, dict):
        raise QuoteError("market data response was not an object")
    return parsed


class HttpTransport:
    """HTTP used by the CLI. Tests pass a fake instead of constructing this."""

    def __init__(self, sender: Any = _post_json, getter: Any = _get_json) -> None:
        self.sender = sender
        self.getter = getter

    def rpc(self, url: str, method: str, params: list[Any]) -> Any:
        if method not in ALLOWED_RPC_METHODS:
            raise GuardError("that RPC method is refused")
        host = _host(url)
        if host in REFUSED_HOSTS or "mainnet" in host:
            raise GuardError("mainnet RPC URL is refused")
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        parsed = self.sender(url, payload)
        if not isinstance(parsed, dict) or "error" in parsed or "result" not in parsed:
            raise QuoteError("market data request was rejected")
        return parsed["result"]

    def get_json(self, url: str) -> Any:
        if url != COINBASE_SOL_USD_SPOT:
            raise GuardError("that price URL is refused")
        parsed = self.getter(url)
        if not isinstance(parsed, dict):
            raise QuoteError("reference price was unreadable")
        return parsed


def parse_sol_usd_spot(payload: Any) -> Decimal:
    if not isinstance(payload, dict):
        raise QuoteError("reference price was unreadable")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise QuoteError("reference price was unreadable")
    amount = data.get("amount")
    if isinstance(amount, bool) or not isinstance(amount, str):
        raise QuoteError("reference price must be a decimal string")
    if data.get("base") != "SOL" or data.get("currency") != "USD":
        raise QuoteError("reference price pair was not SOL-USD")
    try:
        value = Decimal(amount)
    except InvalidOperation:
        raise QuoteError("reference price must be a decimal string") from None
    if not value.is_finite() or value <= 0:
        raise QuoteError("reference price was not positive")
    return value


class MarketReader:
    def __init__(self, config: SwapbotConfig, env: Mapping[str, str], transport: Any) -> None:
        self.config = config
        self.env = env
        self.transport = transport

    def quote(self, chain: ChainConfig, token_in: str, token_out: str, amount: Decimal) -> RawQuote:
        self._known(chain, token_in)
        self._known(chain, token_out)
        if token_in == token_out or self._pool_address(chain, token_in) == self._pool_address(
            chain, token_out
        ):
            raise GuardError("token_in and token_out resolve to the same token")
        if chain.kind == "evm":
            return self._evm(chain, token_in, token_out, amount)
        if chain.kind == "solana":
            return self._solana(chain, token_in, token_out, amount)
        raise GuardError(f"unknown chain {chain.name}")

    def _known(self, chain: ChainConfig, symbol: str) -> None:
        if symbol not in chain.tradeable_symbols():
            raise GuardError(f"{symbol} is not an allowlisted token")

    def _pool_address(self, chain: ChainConfig, symbol: str) -> str:
        if symbol == chain.native_symbol and chain.weth_symbol:
            return chain.tokens[chain.weth_symbol].address
        token = chain.tokens.get(symbol)
        if token is None:
            raise GuardError(f"{symbol} is not an allowlisted token")
        return token.address

    def _decimals(self, chain: ChainConfig, symbol: str) -> int:
        if symbol == chain.native_symbol:
            return chain.native_decimals
        return chain.tokens[symbol].decimals

    def _rpc_url(self, chain: ChainConfig) -> str:
        url = self.env.get(chain.rpc_env_var, "")
        if not url:
            raise GuardError(f"{chain.rpc_env_var} is not set; refusing to continue")
        assert_rpc_url_allowed(url, chain.mainnet_rpc_url)
        return url

    def _require_chain(self, chain: ChainConfig, reported: str) -> None:
        if reported == chain.mainnet_chain_id:
            raise GuardError(f"mainnet chain {reported} is refused")
        if reported != chain.chain_id:
            raise GuardError(f"RPC reports chain {reported}, config expects {chain.chain_id}")

    def _evm(self, chain: ChainConfig, token_in: str, token_out: str, amount: Decimal) -> RawQuote:
        url = self._rpc_url(chain)
        reported = str(_hex_int(self.transport.rpc(url, "eth_chainId", []), "chain id"))
        self._require_chain(chain, reported)
        assert chain.quoter is not None and chain.fee_tier is not None
        data = encode_quote_single(
            self._pool_address(chain, token_in),
            self._pool_address(chain, token_out),
            to_base_units(amount, self._decimals(chain, token_in)),
            chain.fee_tier,
        )
        try:
            result = self.transport.rpc(
                url, "eth_call", [{"to": chain.quoter, "data": "0x" + data.hex()}, "latest"]
            )
        except GuardError:
            raise QuoteError("QuoterV2 quote failed") from None
        if not isinstance(result, str) or not result.startswith("0x"):
            raise QuoteError("QuoterV2 quote failed")
        try:
            payload = bytes.fromhex(result.removeprefix("0x"))
            quoted_base = decode_uint(payload, 0)
            gas_units = decode_uint(payload, 3)
        except AbiError:
            raise QuoteError("QuoterV2 quote failed") from None
        if gas_units == 0:
            if chain.fallback_gas_units is None:
                raise QuoteError("fee estimate was not positive")
            gas_units = chain.fallback_gas_units
        gas_price = _hex_int(self.transport.rpc(url, "eth_gasPrice", []), "gas price")
        return RawQuote(
            quoted_out=from_base_units(quoted_base, self._decimals(chain, token_out)),
            fee_estimate=native_fee(gas_units, gas_price, chain.native_decimals),
            fee_symbol=chain.native_symbol,
            quote_source=QUOTE_SOURCE_POOL,
            price_kind="pool",
        )

    def _solana(
        self, chain: ChainConfig, token_in: str, token_out: str, amount: Decimal
    ) -> RawQuote:
        url = self._rpc_url(chain)
        genesis = self.transport.rpc(url, "getGenesisHash", [])
        if genesis == SOLANA_MAINNET_GENESIS:
            raise GuardError("Solana mainnet is refused")
        if genesis != SOLANA_DEVNET_GENESIS:
            raise GuardError("Solana RPC is not devnet")
        spot = parse_sol_usd_spot(self.transport.get_json(COINBASE_SOL_USD_SPOT))
        out_decimals = self._decimals(chain, token_out)
        quantum = Decimal(1).scaleb(-out_decimals)
        if token_in == "SOL" and token_out == "USDC":
            raw = amount * spot
        elif token_in == "USDC" and token_out == "SOL":
            raw = amount / spot
        else:
            raise GuardError(f"no reference price from {token_in} to {token_out}")
        quoted = raw.quantize(quantum, rounding=ROUND_DOWN)
        if quoted <= 0:
            raise QuoteError("quote returned zero output")
        if chain.fee_estimate_native is None:
            raise QuoteError("fee estimate was not positive")
        return RawQuote(
            quoted_out=quoted,
            fee_estimate=chain.fee_estimate_native,
            fee_symbol=chain.native_symbol,
            quote_source=QUOTE_SOURCE_REFERENCE,
            price_kind="reference",
        )
