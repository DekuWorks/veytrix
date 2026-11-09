"""Store a private research note. This route sizes nothing and submits no order."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from veytrix_api.db import get_db
from veytrix_api.models import ResearchNoteRow, SourceEventRow
from veytrix_api.schemas import (
    ResearchNoteCreate,
    ResearchNoteListResponse,
    ResearchNoteResponse,
    SourceEventCreate,
    SourceEventListResponse,
    SourceEventResponse,
)

router = APIRouter(prefix="/research", tags=["research"])
STORE_UNAVAILABLE = "Research note store is unavailable."


def _timestamp(value: datetime) -> str:
    text = value.astimezone(UTC).isoformat()
    if text.endswith("+00:00"):
        return f"{text[:-6]}Z"
    return text


def _response(row: ResearchNoteRow) -> ResearchNoteResponse:
    title = row.title.strip()
    body = row.body.strip()
    created_at = _timestamp(row.created_at)
    if not title or len(title) > 120 or not body or len(body) > 4000 or "T" not in created_at:
        raise HTTPException(status_code=503, detail=STORE_UNAVAILABLE)
    return ResearchNoteResponse(id=row.id, title=title, body=body, created_at=created_at)


@router.get("/notes", response_model=ResearchNoteListResponse)
def list_notes(db: Session = Depends(get_db)) -> ResearchNoteListResponse:
    try:
        rows = list(
            db.scalars(
                select(ResearchNoteRow).order_by(
                    ResearchNoteRow.created_at.desc(),
                    ResearchNoteRow.id.desc(),
                )
            )
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=STORE_UNAVAILABLE) from exc
    return ResearchNoteListResponse(notes=[_response(row) for row in rows])


@router.post("/notes", response_model=ResearchNoteResponse)
def create_note(
    body: ResearchNoteCreate,
    db: Session = Depends(get_db),
) -> ResearchNoteResponse:
    row = ResearchNoteRow(
        id=uuid4(),
        title=body.title,
        body=body.body,
        created_at=datetime.now(UTC),
    )
    try:
        db.add(row)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=STORE_UNAVAILABLE) from exc
    return _response(row)


@router.delete("/notes/{note_id}", status_code=204)
def delete_note(note_id: UUID, db: Session = Depends(get_db)) -> None:
    try:
        row = db.get(ResearchNoteRow, note_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=STORE_UNAVAILABLE) from exc
    if row is None:
        raise HTTPException(status_code=404, detail="Research note was not found.")
    try:
        db.delete(row)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=STORE_UNAVAILABLE) from exc


EVENT_STORE_UNAVAILABLE = "Source event store is unavailable."


def _event_response(row: SourceEventRow) -> SourceEventResponse:
    title = row.title.strip()
    source = row.source.strip()
    event_time = _timestamp(row.event_time)
    first_public_at = _timestamp(row.first_public_at)
    recorded_at = _timestamp(row.recorded_at)
    if (
        not title
        or len(title) > 120
        or not source
        or len(source) > 200
        or "T" not in event_time
        or "T" not in first_public_at
        or "T" not in recorded_at
    ):
        raise HTTPException(status_code=503, detail=EVENT_STORE_UNAVAILABLE)
    return SourceEventResponse(
        id=row.id,
        title=title,
        source=source,
        event_time=event_time,
        first_public_at=first_public_at,
        recorded_at=recorded_at,
    )


@router.get("/source-events", response_model=SourceEventListResponse)
def list_source_events(db: Session = Depends(get_db)) -> SourceEventListResponse:
    try:
        rows = list(
            db.scalars(
                select(SourceEventRow).order_by(
                    SourceEventRow.recorded_at.desc(),
                    SourceEventRow.id.desc(),
                )
            )
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=EVENT_STORE_UNAVAILABLE) from exc
    return SourceEventListResponse(events=[_event_response(row) for row in rows])


@router.post("/source-events", response_model=SourceEventResponse)
def create_source_event(
    body: SourceEventCreate,
    db: Session = Depends(get_db),
) -> SourceEventResponse:
    row = SourceEventRow(
        id=uuid4(),
        title=body.title,
        source=body.source,
        event_time=body.event_time,
        first_public_at=body.first_public_at,
        recorded_at=datetime.now(UTC),
    )
    try:
        db.add(row)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=EVENT_STORE_UNAVAILABLE) from exc
    return _event_response(row)


@router.delete("/source-events/{event_id}", status_code=204)
def delete_source_event(event_id: UUID, db: Session = Depends(get_db)) -> None:
    try:
        row = db.get(SourceEventRow, event_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=EVENT_STORE_UNAVAILABLE) from exc
    if row is None:
        raise HTTPException(status_code=404, detail="Source event was not found.")
    try:
        db.delete(row)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=EVENT_STORE_UNAVAILABLE) from exc
