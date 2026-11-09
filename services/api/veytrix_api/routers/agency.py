"""Read one local desk. This route cannot enable it, and it cannot submit an order."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from veytrix_api.db import get_db
from veytrix_api.models import AgentPermissionRow, AgentRow
from veytrix_api.schemas import AGENT_CODES, DENIED_TOOLS, DeniedTool, DeskDetailResponse

router = APIRouter(prefix="/agency", tags=["agency"])
REGISTRY_UNAVAILABLE = "Agent registry is unavailable."
DESK_NOT_FOUND = "Desk was not found."
_NOTES_SECRET = re.compile(
    r"(?i)(private[ _-]?key|api[ _-]?key|\bsecret\b|\bpassword\b|"
    r"BEGIN [A-Z ]*PRIVATE|\bsk-|AKIA[0-9A-Z]{8})"
)


def _tools(rows: list[AgentPermissionRow]) -> list[DeniedTool]:
    try:
        ranked = sorted(rows, key=lambda row: DENIED_TOOLS.index(row.tool_name))
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=REGISTRY_UNAVAILABLE) from exc
    return [DeniedTool(tool_name=row.tool_name, effect=row.effect) for row in ranked]


@router.get("/desks/{code}", response_model=DeskDetailResponse)
def read_desk(code: str, db: Session = Depends(get_db)) -> DeskDetailResponse:
    if code not in AGENT_CODES:
        raise HTTPException(status_code=404, detail=DESK_NOT_FOUND)
    try:
        row = db.scalar(select(AgentRow).where(AgentRow.code == code))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=REGISTRY_UNAVAILABLE) from exc
    if row is None:
        raise HTTPException(status_code=404, detail=DESK_NOT_FOUND)
    if _NOTES_SECRET.search(row.notes):
        raise HTTPException(status_code=503, detail=REGISTRY_UNAVAILABLE)
    try:
        permissions = list(
            db.scalars(select(AgentPermissionRow).where(AgentPermissionRow.agent_id == row.id))
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=REGISTRY_UNAVAILABLE) from exc
    try:
        return DeskDetailResponse(
            code=row.code,
            display_name=row.display_name,
            desk=row.desk,
            status=row.status,
            paper_only=row.paper_only,
            can_submit_orders=row.can_submit_orders,
            can_sign=row.can_sign,
            can_transfer_funds=row.can_transfer_funds,
            holds_credentials=row.holds_credentials,
            permission_effect="deny",
            notes=row.notes,
            tools=_tools(permissions),
        )
    except (ValidationError, HTTPException) as exc:
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=503, detail=REGISTRY_UNAVAILABLE) from exc
