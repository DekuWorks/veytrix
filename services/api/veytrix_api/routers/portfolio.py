"""Store a paper size the caller already calculated. This route submits no order."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from veytrix_api.db import get_db
from veytrix_api.models import PaperPositionRow
from veytrix_api.schemas import (
    PaperPositionCreate,
    PaperPositionListResponse,
    PaperPositionResponse,
)
from veytrix_market.coinbase import PRODUCTS

router = APIRouter(prefix="/portfolio", tags=["portfolio"])
STORE_UNAVAILABLE = "Paper position store is unavailable."


def _money(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _timestamp(value: datetime) -> str:
    text = value.astimezone(UTC).isoformat()
    if text.endswith("+00:00"):
        return f"{text[:-6]}Z"
    return text


def _parse_exchange_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _response(row: PaperPositionRow) -> PaperPositionResponse:
    if row.symbol not in PRODUCTS:
        raise HTTPException(status_code=503, detail=STORE_UNAVAILABLE)
    if row.binding_constraint not in ("risk", "allocation", "both", "none"):
        raise HTTPException(status_code=503, detail=STORE_UNAVAILABLE)
    return PaperPositionResponse(
        id=row.id,
        symbol=row.symbol,
        entry=_money(row.entry),
        stop=_money(row.stop),
        shares=row.shares,
        notional=_money(row.notional),
        planned_risk=_money(row.planned_risk),
        binding_constraint=row.binding_constraint,
        exchange_time=_timestamp(row.exchange_time),
        recorded_at=_timestamp(row.recorded_at),
        execution_permitted=False,
        order_submitted=False,
    )


@router.get("/positions", response_model=PaperPositionListResponse)
def list_positions(db: Session = Depends(get_db)) -> PaperPositionListResponse:
    try:
        rows = list(
            db.scalars(select(PaperPositionRow).order_by(PaperPositionRow.recorded_at.desc()))
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=STORE_UNAVAILABLE) from exc
    return PaperPositionListResponse(positions=[_response(row) for row in rows])


@router.post("/positions", response_model=PaperPositionResponse)
def create_position(
    body: PaperPositionCreate,
    db: Session = Depends(get_db),
) -> PaperPositionResponse:
    row = PaperPositionRow(
        id=uuid4(),
        symbol=body.symbol,
        entry=Decimal(body.entry),
        stop=Decimal(body.stop),
        shares=body.shares,
        notional=Decimal(body.notional),
        planned_risk=Decimal(body.planned_risk),
        binding_constraint=body.binding_constraint,
        exchange_time=_parse_exchange_time(body.exchange_time),
        recorded_at=datetime.now(UTC),
    )
    try:
        db.add(row)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=STORE_UNAVAILABLE) from exc
    return _response(row)


@router.delete("/positions/{position_id}", status_code=204)
def delete_position(position_id: UUID, db: Session = Depends(get_db)) -> None:
    try:
        row = db.get(PaperPositionRow, position_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=STORE_UNAVAILABLE) from exc
    if row is None:
        raise HTTPException(status_code=404, detail="Paper position was not found.")
    try:
        db.delete(row)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=STORE_UNAVAILABLE) from exc
