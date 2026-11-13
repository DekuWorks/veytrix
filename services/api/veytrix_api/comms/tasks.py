"""Stored research assignments. A task is not an order and cannot be one."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from veytrix_api.models import ResearchTaskRow


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
) -> ResearchTaskRow:
    row = ResearchTaskRow(
        id=uuid.uuid4(),
        assignee_code=assignee_code,
        assigned_by="SUPERVISOR-01",
        subject=subject[:80],
        instruction=instruction[:500],
        status="assigned",
        conversation_id=conversation_id,
        evidence_message_id=None,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    db.flush()
    return row


def mark_reported(db: Session, task: ResearchTaskRow, message_id: uuid.UUID) -> None:
    """The reply is the evidence. Without that id the task stays assigned."""

    task.status = "reported"
    task.evidence_message_id = message_id
    task.updated_at = _now()
    db.flush()
