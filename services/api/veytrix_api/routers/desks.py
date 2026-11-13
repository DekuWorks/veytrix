"""Desk status and alert acknowledgement. Neither route submits an order."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from veytrix_api.comms.envelope import Safety
from veytrix_api.db import get_db
from veytrix_api.models import AlertAckRow, DeskRunRow, ResearchTaskRow

router = APIRouter(prefix="/desks", tags=["desks"])


class DeskRunOut(BaseModel):
    agent_code: str
    state: str
    source_id: str
    block_reason: str | None
    data_at: str | None
    paper_fill_id: uuid.UUID | None
    heartbeat_at: str


class DeskRunList(Safety):
    desks: list[DeskRunOut]


class AckResult(Safety):
    task_id: uuid.UUID
    status: str
    acknowledged: bool


def _stamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


@router.get("/runs", response_model=DeskRunList)
def list_runs(db: Session = Depends(get_db)) -> DeskRunList:
    rows = list(db.scalars(select(DeskRunRow).order_by(DeskRunRow.agent_code)))
    return DeskRunList(
        desks=[
            DeskRunOut(
                agent_code=row.agent_code,
                state=row.state,
                source_id=row.source_id,
                block_reason=row.block_reason,
                data_at=_stamp(row.data_at),
                paper_fill_id=row.paper_fill_id,
                heartbeat_at=row.heartbeat_at.isoformat(),
            )
            for row in rows
        ]
    )


@router.post("/alerts/{task_id}/ack", response_model=AckResult)
def acknowledge(task_id: uuid.UUID, db: Session = Depends(get_db)) -> AckResult:
    """Record that the founder saw the alert. The task status is not changed."""

    task = db.get(ResearchTaskRow, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")
    before = task.status
    if db.get(AlertAckRow, task_id) is None:
        db.add(AlertAckRow(task_id=task_id, acked_at=datetime.now(UTC)))
    db.commit()
    db.refresh(task)
    if task.status != before:
        raise HTTPException(status_code=500, detail="Acknowledgement changed the task.")
    return AckResult(task_id=task.id, status=task.status, acknowledged=True)
