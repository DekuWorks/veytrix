"""Read the local agent registry. This route cannot enable a desk or submit an order."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from veytrix_api.db import get_db
from veytrix_api.models import AgentRow
from veytrix_api.schemas import AGENT_CODES, AgentDesk, AgentListResponse

router = APIRouter(prefix="/agents", tags=["agents"])
REGISTRY_UNAVAILABLE = "Agent registry is unavailable."


@router.get("", response_model=AgentListResponse)
def list_agents(db: Session = Depends(get_db)) -> AgentListResponse:
    try:
        rows = list(db.scalars(select(AgentRow)))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=REGISTRY_UNAVAILABLE) from exc
    rows.sort(key=lambda row: row.code)
    if [row.code for row in rows] != sorted(AGENT_CODES):
        raise HTTPException(status_code=503, detail=REGISTRY_UNAVAILABLE)
    try:
        agents = [
            AgentDesk(
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
            )
            for row in rows
        ]
        return AgentListResponse(agents=agents)
    except ValidationError as exc:
        raise HTTPException(status_code=503, detail=REGISTRY_UNAVAILABLE) from exc
