"""Read-only monthly distribution projection. This route cannot approve or pay."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from veytrix_api.db import get_db
from veytrix_api.models import Mac01OrderRow
from veytrix_api.routers.strategies import realised_pl
from veytrix_api.schemas import ReminderDatesResponse, TreasuryMonthlySummaryResponse
from veytrix_quant.mac01.config import UnsafeConfiguration, load_config
from veytrix_risk.treasury import TreasuryInputError, close_date, project_month, review_date

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


REMINDER_NOTE = (
    "Local dates only. No DayPilot event was created. The Wednesday meeting time is "
    "still unconfirmed. This cannot approve a payout."
)


@router.get("/reminders", response_model=ReminderDatesResponse)
def reminder_dates(
    year: int = Query(ge=2000, le=2100),
    month: int = Query(ge=1, le=12),
) -> ReminderDatesResponse:
    """Return the next close and review dates. The route creates no event."""

    try:
        close = close_date(year, month)
        review = review_date(year, month)
    except TreasuryInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    raw_close_day = 1
    raw_review_day = 5
    return ReminderDatesResponse(
        period=f"{year:04d}-{month:02d}",
        accounting_close_on=close.isoformat(),
        accounting_close_shifted_for_weekend=close.day != raw_close_day,
        payout_review_on=review.isoformat(),
        payout_review_shifted_for_weekend=review.day != raw_review_day,
        meeting_time="unconfirmed",
        daypilot="absent",
        event_created=False,
        transfer_submitted=False,
        execution_permitted=False,
        order_submitted=False,
        source="local_calendar",
        note=REMINDER_NOTE,
    )
