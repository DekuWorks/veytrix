"""Read-only monthly distribution projection. This route cannot approve or pay."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from veytrix_api.db import get_db
from veytrix_api.models import Mac01OrderRow
from veytrix_api.routers.strategies import realised_pl
from veytrix_api.schemas import TreasuryMonthlySummaryResponse
from veytrix_quant.mac01.config import UnsafeConfiguration, load_config
from veytrix_risk.treasury import project_month, review_date

router = APIRouter(prefix="/treasury", tags=["treasury"])
SUMMARY_UNAVAILABLE = "Treasury summary is unavailable."
NEW_YORK = ZoneInfo("America/New_York")
NOTE = (
    "Local projection from paper MAC-01 fills in this database, FIFO, before fees. "
    "Loss carryforward is not stored, so this month starts from zero. "
    "This is not a broker balance, not a settlement, and not a transfer. "
    "No approval route exists."
)


def _money(value: Decimal) -> str:
    return format(value, "f")


@router.get("/monthly-summary", response_model=TreasuryMonthlySummaryResponse)
def monthly_summary(db: Session = Depends(get_db)) -> TreasuryMonthlySummaryResponse:
    """Project the open New York month. Live mode and a broken ledger return 503."""

    try:
        config = load_config()
    except UnsafeConfiguration as exc:
        raise HTTPException(status_code=503, detail=SUMMARY_UNAVAILABLE) from exc
    if config.mode != "paper":
        raise HTTPException(status_code=503, detail=SUMMARY_UNAVAILABLE)
    try:
        rows = list(db.scalars(select(Mac01OrderRow).order_by(Mac01OrderRow.created_at.asc())))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=SUMMARY_UNAVAILABLE) from exc
    paper = [row for row in rows if row.mode == "paper"]
    realised, filled = realised_pl(paper)
    if realised is None:
        raise HTTPException(status_code=503, detail=SUMMARY_UNAVAILABLE)
    projection = project_month(
        realised_profit=realised,
        costs=Decimal("0"),
        loss_carryforward=Decimal("0"),
    )
    today = datetime.now(NEW_YORK).date()
    review = review_date(today.year, today.month)
    fifth = review.replace(day=5) if review.day != 5 else review
    return TreasuryMonthlySummaryResponse(
        period=f"{today.year:04d}-{today.month:02d}",
        period_closed=False,
        realised_profit=_money(projection.realised_profit),
        costs=_money(projection.costs),
        loss_carryforward=_money(projection.loss_carryforward),
        eligible_profit=_money(projection.eligible_profit),
        proposed_distribution=_money(projection.proposed_distribution),
        retained=_money(projection.retained),
        loss_carryforward_out=_money(projection.loss_carryforward_out),
        distribution_fraction="0.50",
        distribution_cap="2000.00",
        review_day=5,
        review_on=review.isoformat(),
        review_shifted_for_weekend=review != fifth,
        fills_counted=filled,
        fees_included=False,
        carryforward_stored=False,
        broker_reconciled=False,
        settled=False,
        transfer_status="not_attempted",
        approval_route="absent",
        execution_permitted=False,
        order_submitted=False,
        transfer_submitted=False,
        source="local_projection",
        note=NOTE,
    )
