"""Append one audit row for a size the API already calculated.

The row records the correlation id from the request middleware. It does not
submit an order, and the payload cannot say that execution was permitted.
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from veytrix_api.logging_config import correlation_id_var
from veytrix_api.models import AuditEvent

SIZE_RECORDED = "risk.size.recorded"


class AuditWriteError(Exception):
    """The size was calculated, but it cannot be stored without an audit row."""


def current_correlation_id() -> str:
    value = correlation_id_var.get()
    if value is None or not 1 <= len(value) <= 64:
        raise AuditWriteError("correlation id is missing")
    return value


def record_size(
    db: Session,
    *,
    symbol: str,
    shares: int,
    binding_constraint: str,
) -> None:
    db.add(
        AuditEvent(
            id=uuid4(),
            correlation_id=current_correlation_id(),
            action=SIZE_RECORDED,
            payload={
                "symbol": symbol,
                "shares": shares,
                "binding_constraint": binding_constraint,
                "execution_permitted": False,
                "order_submitted": False,
            },
        )
    )
