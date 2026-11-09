"""Persist simulated swaps. The tables hold balances and receipts, never keys."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from veytrix_ai.config import ChainConfig, SwapbotConfig
from veytrix_ai.guards import GuardError, decimal_text
from veytrix_api.models import (
    BlockchainNetworkRow,
    PaperSwapFillRow,
    PaperSwapOrderRow,
    SimulatedWalletBalanceRow,
)


def _dec(value: Decimal) -> Decimal:
    return Decimal(str(value))


def ensure_network(session: Session, chain: ChainConfig) -> BlockchainNetworkRow:
    row = session.scalar(
        select(BlockchainNetworkRow).where(BlockchainNetworkRow.name == chain.name)
    )
    if row is None:
        row = BlockchainNetworkRow(
            id=uuid.uuid4(),
            name=chain.name,
            network=chain.network,
            chain_id=chain.chain_id,
            simulated=True,
            created_at=datetime.now(UTC),
        )
        session.add(row)
        session.flush()
        return row
    if row.chain_id != chain.chain_id or row.network != chain.network or not row.simulated:
        raise GuardError("stored network does not match the testnet config")
    return row


def ensure_balances(session: Session, network: BlockchainNetworkRow, chain: ChainConfig) -> None:
    rows = list(
        session.scalars(
            select(SimulatedWalletBalanceRow).where(
                SimulatedWalletBalanceRow.network_id == network.id
            )
        )
    )
    have = {row.symbol for row in rows}
    now = datetime.now(UTC)
    for symbol, amount in chain.starting_balances.items():
        if symbol in have:
            continue
        session.add(
            SimulatedWalletBalanceRow(
                id=uuid.uuid4(),
                network_id=network.id,
                symbol=symbol,
                amount=amount,
                updated_at=now,
            )
        )
    session.flush()


def balance_map(session: Session, network_id: uuid.UUID) -> dict[str, Decimal]:
    rows = session.scalars(
        select(SimulatedWalletBalanceRow).where(SimulatedWalletBalanceRow.network_id == network_id)
    )
    return {row.symbol: _dec(row.amount) for row in rows}


def prepare_wallet(session: Session, config: SwapbotConfig) -> dict[str, dict[str, Decimal]]:
    snapshot: dict[str, dict[str, Decimal]] = {}
    for chain in config.chains.values():
        network = ensure_network(session, chain)
        ensure_balances(session, network, chain)
        snapshot[chain.name] = balance_map(session, network.id)
    session.commit()
    return snapshot


def _set_balance(
    session: Session,
    network_id: uuid.UUID,
    symbol: str,
    amount: Decimal,
    existing: dict[str, SimulatedWalletBalanceRow],
) -> None:
    if amount < 0:
        raise GuardError(f"insufficient {symbol} balance")
    now = datetime.now(UTC)
    row = existing.get(symbol)
    if row is None:
        session.add(
            SimulatedWalletBalanceRow(
                id=uuid.uuid4(),
                network_id=network_id,
                symbol=symbol,
                amount=amount,
                updated_at=now,
            )
        )
        return
    row.amount = amount
    row.updated_at = now


def record_swap(
    session: Session,
    chain: ChainConfig,
    *,
    token_in: str,
    token_out: str,
    amount_in: Decimal,
    quoted_out: Decimal,
    amount_out: Decimal,
    quoted_price: Decimal,
    slippage_bps: int,
    slippage_applied: Decimal,
    fee_estimate: Decimal,
    fee_symbol: str,
    quote_source: str,
    price_kind: str,
    balances_after: dict[str, Decimal],
) -> str:
    network = ensure_network(session, chain)
    rows = list(
        session.scalars(
            select(SimulatedWalletBalanceRow).where(
                SimulatedWalletBalanceRow.network_id == network.id
            )
        )
    )
    existing = {row.symbol: row for row in rows}
    now = datetime.now(UTC)
    order_id = uuid.uuid4()
    stored_balances = {symbol: decimal_text(amount) for symbol, amount in balances_after.items()}
    try:
        for symbol, amount in balances_after.items():
            _set_balance(session, network.id, symbol, amount, existing)
        # Network row is already flushed. Persist balances, then the order,
        # before the fill is added. Postgres enforces fk_paper_swap_fills_order_id
        # and SQLAlchemy has no relationship() to sort those inserts. One commit
        # at the end, so a failure still rolls the whole ledger change back.
        session.flush()
        session.add(
            PaperSwapOrderRow(
                id=order_id,
                network_id=network.id,
                token_in=token_in,
                token_out=token_out,
                amount_in=amount_in,
                quoted_out=quoted_out,
                amount_out=amount_out,
                quoted_price=quoted_price,
                slippage_bps=slippage_bps,
                slippage_applied=slippage_applied,
                fee_estimate=fee_estimate,
                fee_symbol=fee_symbol,
                quote_source=quote_source,
                price_kind=price_kind,
                status="simulated",
                simulated=True,
                created_at=now,
            )
        )
        session.flush()
        session.add(
            PaperSwapFillRow(
                id=uuid.uuid4(),
                order_id=order_id,
                amount_in=amount_in,
                amount_out=amount_out,
                fee_estimate=fee_estimate,
                slippage_applied=slippage_applied,
                quoted_price=quoted_price,
                quote_source=quote_source,
                simulated=True,
                balances_after=stored_balances,
                created_at=now,
            )
        )
        session.commit()
    except GuardError:
        session.rollback()
        raise
    except Exception:
        session.rollback()
        raise GuardError("paper swap ledger is unavailable") from None
    return str(order_id)
