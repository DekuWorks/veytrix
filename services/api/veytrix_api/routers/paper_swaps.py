"""Read the simulated paper-swap ledger. This router does not place a swap."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from veytrix_api.db import get_db
from veytrix_api.models import (
    BlockchainNetworkRow,
    PaperSwapFillRow,
    PaperSwapOrderRow,
    SimulatedWalletBalanceRow,
)
from veytrix_api.schemas import (
    PaperSwapBalance,
    PaperSwapNetwork,
    PaperSwapOrderEntry,
    PaperSwapOrderListResponse,
    PaperSwapPortfolioResponse,
)

router = APIRouter(prefix="/paper-swaps", tags=["paper-swaps"])
LEDGER_UNAVAILABLE = "Paper swap ledger is unavailable."
ORDER_LIMIT = 100


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    text = value.astimezone(UTC).isoformat()
    return f"{text[:-6]}Z" if text.endswith("+00:00") else text


def _money(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _unavailable() -> HTTPException:
    return HTTPException(status_code=503, detail=LEDGER_UNAVAILABLE)


@router.get("/portfolio", response_model=PaperSwapPortfolioResponse)
def portfolio(db: Session = Depends(get_db)) -> PaperSwapPortfolioResponse:
    try:
        networks = list(
            db.scalars(select(BlockchainNetworkRow).order_by(BlockchainNetworkRow.name))
        )
        balances = list(db.scalars(select(SimulatedWalletBalanceRow)))
    except Exception as exc:
        raise _unavailable() from exc
    by_network: dict[object, list[SimulatedWalletBalanceRow]] = {}
    for row in balances:
        by_network.setdefault(row.network_id, []).append(row)
    payload: list[PaperSwapNetwork] = []
    for network in networks:
        if network.name not in ("solana", "ethereum", "base") or not network.simulated:
            raise HTTPException(status_code=503, detail=LEDGER_UNAVAILABLE)
        if network.network not in ("solana-devnet", "sepolia", "base-sepolia"):
            raise HTTPException(status_code=503, detail=LEDGER_UNAVAILABLE)
        if network.chain_id not in ("devnet", "11155111", "84532"):
            raise HTTPException(status_code=503, detail=LEDGER_UNAVAILABLE)
        rows = sorted(by_network.get(network.id, []), key=lambda item: item.symbol)
        payload.append(
            PaperSwapNetwork(
                chain=network.name,  # type: ignore[arg-type]
                network=network.network,  # type: ignore[arg-type]
                chain_id=network.chain_id,
                simulated=True,
                balances=[
                    PaperSwapBalance(symbol=row.symbol, amount=_money(row.amount)) for row in rows
                ],
            )
        )
    return PaperSwapPortfolioResponse(networks=payload)


@router.get("/orders", response_model=PaperSwapOrderListResponse)
def orders(db: Session = Depends(get_db)) -> PaperSwapOrderListResponse:
    try:
        rows = list(
            db.scalars(
                select(PaperSwapOrderRow)
                .order_by(PaperSwapOrderRow.created_at.desc())
                .limit(ORDER_LIMIT)
            )
        )
        networks = {row.id: row for row in db.scalars(select(BlockchainNetworkRow))}
        fills = {row.order_id: row for row in db.scalars(select(PaperSwapFillRow))}
    except Exception as exc:
        raise _unavailable() from exc
    entries: list[PaperSwapOrderEntry] = []
    for row in rows:
        network = networks.get(row.network_id)
        fill = fills.get(row.id)
        if (
            network is None
            or fill is None
            or not row.simulated
            or row.status != "simulated"
            or not fill.simulated
            or network.name not in ("solana", "ethereum", "base")
            or network.network not in ("solana-devnet", "sepolia", "base-sepolia")
            or network.chain_id not in ("devnet", "11155111", "84532")
            or row.price_kind not in ("pool", "reference")
        ):
            raise HTTPException(status_code=503, detail=LEDGER_UNAVAILABLE)
        balances = fill.balances_after if isinstance(fill.balances_after, dict) else None
        if balances is None or any(not isinstance(value, str) for value in balances.values()):
            raise HTTPException(status_code=503, detail=LEDGER_UNAVAILABLE)
        entries.append(
            PaperSwapOrderEntry(
                id=row.id,
                chain=network.name,  # type: ignore[arg-type]
                network=network.network,  # type: ignore[arg-type]
                chain_id=network.chain_id,
                token_in=row.token_in,
                token_out=row.token_out,
                amount_in=_money(row.amount_in),
                quoted_out=_money(row.quoted_out),
                amount_out=_money(row.amount_out),
                quoted_price=_money(row.quoted_price),
                quote_source=row.quote_source,
                price_kind=row.price_kind,  # type: ignore[arg-type]
                slippage_bps=row.slippage_bps,
                slippage_applied=_money(row.slippage_applied),
                fee_estimate=_money(row.fee_estimate),
                fee_symbol=row.fee_symbol,
                balances_after=balances,
                status="simulated",
                simulated=True,
                created_at=_timestamp(row.created_at),
            )
        )
    return PaperSwapOrderListResponse(orders=entries)
