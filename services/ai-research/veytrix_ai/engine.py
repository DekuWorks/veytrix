"""Simulated swap accounting. Quotes are read-only. Nothing is signed or sent."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from veytrix_ai.config import ChainConfig, SwapbotConfig
from veytrix_ai.guards import (
    GuardError,
    KillSwitch,
    apply_slippage,
    decimal_text,
    effective_slippage_bps,
    parse_amount,
)
from veytrix_ai.quote import MarketReader, RawQuote
from veytrix_ai.store import (
    balance_map,
    ensure_balances,
    ensure_network,
    prepare_wallet,
    record_swap,
)


def _decimals(chain: ChainConfig, symbol: str) -> int:
    if symbol == chain.native_symbol:
        return chain.native_decimals
    token = chain.tokens.get(symbol)
    if token is None:
        raise GuardError(f"{symbol} is not an allowlisted token")
    return token.decimals


def project_balances(
    chain: ChainConfig,
    balances: dict[str, Decimal],
    token_in: str,
    token_out: str,
    amount_in: Decimal,
    amount_out: Decimal,
    fee: Decimal,
) -> dict[str, Decimal]:
    updated = dict(balances)
    updated.setdefault(token_in, Decimal(0))
    updated.setdefault(token_out, Decimal(0))
    updated.setdefault(chain.native_symbol, Decimal(0))
    if token_in == chain.native_symbol:
        debit = amount_in + fee
        if updated[token_in] < debit:
            raise GuardError(f"insufficient {token_in} balance")
        updated[token_in] -= debit
        updated[token_out] += amount_out
        return updated
    if updated[token_in] < amount_in:
        raise GuardError(f"insufficient {token_in} balance")
    if updated[chain.native_symbol] < fee:
        raise GuardError(f"insufficient {chain.native_symbol} balance for the fee estimate")
    updated[token_in] -= amount_in
    updated[chain.native_symbol] -= fee
    updated[token_out] += amount_out
    return updated


class SwapEngine:
    def __init__(
        self,
        config: SwapbotConfig,
        reader: MarketReader,
        kill_switch: KillSwitch,
        session: Session | None = None,
    ) -> None:
        self.config = config
        self.reader = reader
        self.kill_switch = kill_switch
        self.session = session

    def chain(self, name: str) -> ChainConfig:
        chain = self.config.chains.get(name)
        if chain is None:
            raise GuardError(f"unknown chain {name}")
        return chain

    def _fields(
        self,
        chain: ChainConfig,
        token_in: str,
        token_out: str,
        amount: Decimal,
        slippage_bps: int,
        raw: RawQuote,
    ) -> dict[str, Any]:
        amount_out = apply_slippage(raw.quoted_out, slippage_bps, _decimals(chain, token_out))
        slippage_applied = raw.quoted_out - amount_out
        if slippage_applied < 0:
            raise GuardError("slippage was negative")
        return {
            "simulated": True,
            "signing": False,
            "broadcast": False,
            "chain": chain.name,
            "network": chain.network,
            "chain_id": chain.chain_id,
            "token_in": token_in,
            "token_out": token_out,
            "amount_in": decimal_text(amount),
            "quoted_out": decimal_text(raw.quoted_out),
            "amount_out": decimal_text(amount_out),
            "quoted_price": decimal_text(raw.quoted_out / amount),
            "quote_source": raw.quote_source,
            "price_kind": raw.price_kind,
            "slippage_bps": slippage_bps,
            "slippage_applied": decimal_text(slippage_applied),
            "fee_estimate": decimal_text(raw.fee_estimate),
            "fee_symbol": raw.fee_symbol,
            "amount_out_decimal": amount_out,
            "quoted_out_decimal": raw.quoted_out,
            "quoted_price_decimal": raw.quoted_out / amount,
            "slippage_applied_decimal": slippage_applied,
            "fee_decimal": raw.fee_estimate,
        }

    def quote(
        self,
        chain_name: str,
        token_in: str,
        token_out: str,
        amount: str | Decimal,
        slippage_bps: int | None = None,
    ) -> dict[str, Any]:
        self.kill_switch.check()
        chain = self.chain(chain_name)
        value = parse_amount(amount)
        bps = effective_slippage_bps(self.config, slippage_bps)
        raw = self.reader.quote(chain, token_in, token_out, value)
        fields = self._fields(chain, token_in, token_out, value, bps, raw)
        public = {key: item for key, item in fields.items() if not key.endswith("_decimal")}
        return {**public, "recorded": False, "status": "quoted"}

    def swap(
        self,
        chain_name: str,
        token_in: str,
        token_out: str,
        amount: str | Decimal,
        slippage_bps: int | None = None,
    ) -> dict[str, Any]:
        self.kill_switch.check()
        if self.session is None:
            raise GuardError("paper swap ledger is unavailable")
        chain = self.chain(chain_name)
        value = parse_amount(amount)
        bps = effective_slippage_bps(self.config, slippage_bps)
        raw = self.reader.quote(chain, token_in, token_out, value)
        fields = self._fields(chain, token_in, token_out, value, bps, raw)
        try:
            network = ensure_network(self.session, chain)
            ensure_balances(self.session, network, chain)
            current = balance_map(self.session, network.id)
            updated = project_balances(
                chain,
                current,
                token_in,
                token_out,
                value,
                fields["amount_out_decimal"],
                fields["fee_decimal"],
            )
        except GuardError:
            self.session.rollback()
            raise
        order_id = record_swap(
            self.session,
            chain,
            token_in=token_in,
            token_out=token_out,
            amount_in=value,
            quoted_out=fields["quoted_out_decimal"],
            amount_out=fields["amount_out_decimal"],
            quoted_price=fields["quoted_price_decimal"],
            slippage_bps=bps,
            slippage_applied=fields["slippage_applied_decimal"],
            fee_estimate=fields["fee_decimal"],
            fee_symbol=raw.fee_symbol,
            quote_source=raw.quote_source,
            price_kind=raw.price_kind,
            balances_after=updated,
        )
        public = {key: item for key, item in fields.items() if not key.endswith("_decimal")}
        return {
            **public,
            "recorded": True,
            "status": "simulated",
            "order_id": order_id,
            "balances": {
                symbol: decimal_text(amount) for symbol, amount in sorted(updated.items())
            },
        }

    def portfolio(self) -> dict[str, Any]:
        if self.session is None:
            raise GuardError("paper swap ledger is unavailable")
        snapshot = prepare_wallet(self.session, self.config)
        networks = []
        for name, chain in self.config.chains.items():
            balances = snapshot.get(name, {})
            networks.append(
                {
                    "chain": chain.name,
                    "network": chain.network,
                    "chain_id": chain.chain_id,
                    "simulated": True,
                    "balances": {
                        symbol: decimal_text(amount) for symbol, amount in sorted(balances.items())
                    },
                }
            )
        return {
            "simulated": True,
            "signing": False,
            "broadcast": False,
            "kill_switch": "engaged" if self.kill_switch.engaged else "clear",
            "networks": networks,
        }

    def status(self) -> dict[str, Any]:
        return {
            "simulated": True,
            "signing": False,
            "broadcast": False,
            "kill_switch": "engaged" if self.kill_switch.engaged else "clear",
            "chains": sorted(self.config.chains),
            "order_route": "cli_only",
        }
