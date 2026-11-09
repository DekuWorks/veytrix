"""Calculate a paper share count and record that result locally. This route submits no order."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from veytrix_api.audit_log import record_size
from veytrix_api.db import get_db
from veytrix_api.deps import get_policy
from veytrix_api.models import PaperSizeJournalRow
from veytrix_api.schemas import SizeRequest, SizeResponse
from veytrix_risk.sizing import RiskPolicy, SizingError, size_position

router = APIRouter(prefix="/risk", tags=["risk"])
JOURNAL_UNAVAILABLE = "Paper size journal is unavailable."


def _money(value: Decimal) -> str:
    return format(value, "f")


@router.post("/size", response_model=SizeResponse)
def size_endpoint(
    body: SizeRequest,
    policy: RiskPolicy = Depends(get_policy),
    db: Session = Depends(get_db),
) -> SizeResponse:
    try:
        result = size_position(
            body.account_equity,
            body.entry_price,
            body.stop_price,
            side=body.side,
            risk_fraction=body.risk_fraction,
            max_allocation_fraction=body.max_allocation_fraction,
            policy=policy,
        )
    except SizingError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    response = SizeResponse(
        symbol=body.symbol,
        shares=result.shares,
        binding_constraint=result.binding_constraint,
        stop_distance=_money(result.stop_distance),
        planned_risk_amount=_money(result.planned_risk_amount),
        risk_budget=_money(result.risk_budget),
        notional=_money(result.notional),
        account_equity=_money(result.account_equity),
        entry_price=_money(result.entry_price),
        stop_price=_money(result.stop_price),
        risk_fraction=_money(result.risk_fraction),
        max_allocation_fraction=_money(result.max_allocation_fraction),
        daily_loss_stop_fraction=_money(result.daily_loss_stop_fraction),
        weekly_loss_stop_fraction=_money(result.weekly_loss_stop_fraction),
        policy_name=result.policy_name,
        warning=result.warning,
        note=result.note,
        execution_permitted=False,
        order_submitted=False,
        daily_stop_enforced=False,
        weekly_stop_enforced=False,
    )
    row = PaperSizeJournalRow(
        id=uuid4(),
        recorded_at=datetime.now(UTC),
        symbol=response.symbol,
        equity=Decimal(response.account_equity),
        entry=Decimal(response.entry_price),
        stop=Decimal(response.stop_price),
        shares=response.shares,
        planned_risk=Decimal(response.planned_risk_amount),
        binding_constraint=response.binding_constraint,
        execution_permitted=False,
        order_submitted=False,
    )
    try:
        db.add(row)
        record_size(
            db,
            symbol=response.symbol,
            shares=response.shares,
            binding_constraint=response.binding_constraint,
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=JOURNAL_UNAVAILABLE) from exc
    return response
