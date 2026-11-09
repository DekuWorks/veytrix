"""Read local audit rows. These routes do not calculate a size or submit an order."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from veytrix_api.db import get_db
from veytrix_api.models import AuditEvent, PaperSizeJournalRow
from veytrix_api.schemas import (
    AuditLogEntry,
    AuditLogListResponse,
    PaperSizeJournalEntry,
    PaperSizeJournalListResponse,
)
from veytrix_market.coinbase import PRODUCTS

router = APIRouter(prefix="/audit", tags=["audit"])
JOURNAL_UNAVAILABLE = "Paper size journal is unavailable."
AUDIT_UNAVAILABLE = "Audit log is unavailable."
JOURNAL_LIMIT = 20
AUDIT_LIMIT = 20
SIZE_RECORDED = "risk.size.recorded"
_PAYLOAD_KEYS = frozenset(
    {"symbol", "shares", "binding_constraint", "execution_permitted", "order_submitted"}
)
_CORRELATION_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_BINDING = frozenset({"risk", "allocation", "both", "none"})


def _money(value: Decimal) -> str:
    return format(value, "f")


def _timestamp(value: datetime) -> str:
    text = value.astimezone(UTC).isoformat()
    if text.endswith("+00:00"):
        return f"{text[:-6]}Z"
    return text


def _entry(row: PaperSizeJournalRow) -> PaperSizeJournalEntry:
    if row.symbol not in PRODUCTS:
        raise HTTPException(status_code=503, detail=JOURNAL_UNAVAILABLE)
    if row.binding_constraint not in ("risk", "allocation", "both", "none"):
        raise HTTPException(status_code=503, detail=JOURNAL_UNAVAILABLE)
    if row.execution_permitted or row.order_submitted:
        raise HTTPException(status_code=503, detail=JOURNAL_UNAVAILABLE)
    return PaperSizeJournalEntry(
        id=row.id,
        recorded_at=_timestamp(row.recorded_at),
        symbol=row.symbol,
        equity=_money(row.equity),
        entry=_money(row.entry),
        stop=_money(row.stop),
        shares=row.shares,
        planned_risk=_money(row.planned_risk),
        binding_constraint=row.binding_constraint,
        execution_permitted=False,
        order_submitted=False,
    )


@router.get("/size-journal", response_model=PaperSizeJournalListResponse)
def list_size_journal(db: Session = Depends(get_db)) -> PaperSizeJournalListResponse:
    try:
        rows = list(
            db.scalars(
                select(PaperSizeJournalRow)
                .order_by(PaperSizeJournalRow.recorded_at.desc(), PaperSizeJournalRow.id.desc())
                .limit(JOURNAL_LIMIT)
            )
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=JOURNAL_UNAVAILABLE) from exc
    return PaperSizeJournalListResponse(entries=[_entry(row) for row in rows])


def _audit_entry(row: AuditEvent) -> AuditLogEntry:
    payload = row.payload
    if not isinstance(payload, dict) or set(payload) != _PAYLOAD_KEYS:
        raise HTTPException(status_code=503, detail=AUDIT_UNAVAILABLE)
    if row.action != SIZE_RECORDED or not _CORRELATION_ID.fullmatch(row.correlation_id):
        raise HTTPException(status_code=503, detail=AUDIT_UNAVAILABLE)
    if payload["symbol"] not in PRODUCTS or payload["binding_constraint"] not in _BINDING:
        raise HTTPException(status_code=503, detail=AUDIT_UNAVAILABLE)
    shares = payload["shares"]
    if isinstance(shares, bool) or not isinstance(shares, int) or shares < 0:
        raise HTTPException(status_code=503, detail=AUDIT_UNAVAILABLE)
    if payload["execution_permitted"] is not False or payload["order_submitted"] is not False:
        raise HTTPException(status_code=503, detail=AUDIT_UNAVAILABLE)
    return AuditLogEntry(
        id=row.id,
        created_at=_timestamp(row.created_at),
        correlation_id=row.correlation_id,
        action=SIZE_RECORDED,
        symbol=payload["symbol"],
        shares=shares,
        binding_constraint=payload["binding_constraint"],
        execution_permitted=False,
        order_submitted=False,
    )


@router.get("/log", response_model=AuditLogListResponse)
def list_audit_log(db: Session = Depends(get_db)) -> AuditLogListResponse:
    """Newest size-audit rows. One unsafe payload hides the list."""

    try:
        rows = list(
            db.scalars(
                select(AuditEvent)
                .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
                .limit(AUDIT_LIMIT)
            )
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=AUDIT_UNAVAILABLE) from exc
    try:
        return AuditLogListResponse(events=[_audit_entry(row) for row in rows])
    except ValidationError as exc:
        raise HTTPException(status_code=503, detail=AUDIT_UNAVAILABLE) from exc
