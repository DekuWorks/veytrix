"""Stored research assignments. A task is not an order and cannot be one.

States are queued, running, blocked, completed, and failed. Completed is
allowed only when an evidence message id is stored with the row.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from veytrix_api.models import ResearchTaskRow

OPEN = ("queued", "running")
TERMINAL = ("blocked", "completed", "failed")


def _now() -> datetime:
    return datetime.now(UTC)


def list_for(db: Session, code: str) -> list[ResearchTaskRow]:
    return list(
        db.scalars(
            select(ResearchTaskRow)
            .where(ResearchTaskRow.assignee_code == code)
            .order_by(ResearchTaskRow.created_at.desc())
        )
    )


def create(
    db: Session,
    *,
    assignee_code: str,
    subject: str,
    instruction: str,
    conversation_id: uuid.UUID | None,
    kind: str = "research",
    correlation_id: str | None = None,
) -> ResearchTaskRow:
    row = ResearchTaskRow(
        id=uuid.uuid4(),
        assignee_code=assignee_code,
        assigned_by="SUPERVISOR-01",
        subject=subject[:80],
        instruction=instruction[:500],
        status="queued",
        kind=kind,
        attempt_count=0,
        max_attempts=2,
        worker_id=None,
        blocked_reason=None,
        correlation_id=correlation_id,
        conversation_id=conversation_id,
        evidence_message_id=None,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    db.flush()
    return row


def mark_blocked(
    db: Session, task: ResearchTaskRow, message_id: uuid.UUID | None, reason: str
) -> None:
    task.status = "blocked"
    task.evidence_message_id = message_id
    task.blocked_reason = reason[:200]
    task.worker_id = None
    task.updated_at = _now()
    db.flush()


def mark_completed(db: Session, task: ResearchTaskRow, message_id: uuid.UUID) -> None:
    """Completed requires the message that holds the finding. No message, no completion."""

    if message_id is None:
        raise ValueError("completed requires an evidence message")
    task.status = "completed"
    task.evidence_message_id = message_id
    task.blocked_reason = None
    task.worker_id = None
    task.updated_at = _now()
    db.flush()


def mark_failed(db: Session, task: ResearchTaskRow, reason: str) -> None:
    task.status = "failed"
    task.blocked_reason = reason[:200]
    task.worker_id = None
    task.updated_at = _now()
    db.flush()


def requeue(db: Session, task: ResearchTaskRow) -> None:
    task.attempt_count = min(task.attempt_count + 1, 3)
    task.status = "queued" if task.attempt_count < task.max_attempts else "failed"
    if task.status == "failed":
        task.blocked_reason = "provider_failed"
    task.worker_id = None
    task.updated_at = _now()
    db.flush()
