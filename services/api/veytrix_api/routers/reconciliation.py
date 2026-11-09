"""Read the local MAC-01 order rows against an unread broker. This route submits nothing."""

from __future__ import annotations

import re
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from veytrix_api.db import get_db
from veytrix_api.models import Mac01OrderRow
from veytrix_api.schemas import (
    LOCAL_ORDER_STATUSES,
    TERMINAL_ORDER_STATUSES,
    ReconciliationResponse,
    ReconciliationRow,
)

router = APIRouter(prefix="/ledger", tags=["ledger"])
UNAVAILABLE = "Local reconciliation is unavailable."
ROW_LIMIT = 100
_CLIENT_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_BROKER_ID = re.compile(r"^[A-Za-z0-9-]{1,64}$")
NOTE = (
    "These rows are the local MAC-01 ledger. The broker account was not read, "
    "so nothing here is reconciled. Not investment advice."
)


def _unavailable() -> HTTPException:
    return HTTPException(status_code=503, detail=UNAVAILABLE)


def _row(row: Mac01OrderRow) -> ReconciliationRow:
    broker_id = row.broker_order_id
    if row.mode not in ("paper", "live") or row.side not in ("buy", "sell"):
        raise _unavailable()
    if row.status not in LOCAL_ORDER_STATUSES or not _CLIENT_ID.fullmatch(row.client_order_id):
        raise _unavailable()
    if broker_id is not None and not _BROKER_ID.fullmatch(broker_id):
        raise _unavailable()
    if not isinstance(row.filled_qty, Decimal) or row.filled_qty < 0:
        raise _unavailable()
    return ReconciliationRow(
        client_order_id=row.client_order_id,
        mode=row.mode,
        side=row.side,
        local_status=row.status,
        broker_order_id=broker_id,
        broker_order_stored=broker_id is not None,
        broker_status="not_read",
        matched=False,
        reason="broker_not_read",
    )


@router.get("/reconciliation", response_model=ReconciliationResponse)
def reconciliation(db: Session = Depends(get_db)) -> ReconciliationResponse:
    """Local orders only. The broker side of every row stays unread."""

    try:
        rows = list(
            db.scalars(
                select(Mac01OrderRow).order_by(Mac01OrderRow.created_at.desc()).limit(ROW_LIMIT)
            )
        )
    except Exception as exc:
        raise _unavailable() from exc
    projected = [_row(row) for row in rows]
    fills = sum(1 for row in rows if row.filled_qty > 0)
    open_rows = sum(1 for row in rows if row.status not in TERMINAL_ORDER_STATUSES)
    return ReconciliationResponse(
        local_orders=len(projected),
        local_fills=fills,
        local_open=open_rows,
        broker_rows_read=0,
        broker_read="absent",
        alpaca_called=False,
        reconciled=False,
        rows=projected,
        execution_permitted=False,
        order_submitted=False,
        order_route="absent",
        source="local_ledger",
        note=NOTE,
    )
