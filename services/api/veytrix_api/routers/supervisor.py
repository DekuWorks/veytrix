"""List local supervisor tools and check a name. Nothing here runs a tool."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from veytrix_api.schemas import (
    ToolCatalogueResponse,
    ToolCheckRequest,
    ToolCheckResponse,
    ToolSpecResponse,
)
from veytrix_api.tool_gate import ToolInputError, catalogue, check_tool_call

router = APIRouter(prefix="/supervisor", tags=["supervisor"])
CATALOGUE_NOTE = (
    "Local tool catalogue. Chat is not configured. A check does not run the tool, "
    "call a model, or submit an order."
)
CHECK_NOTE = (
    "This check did not run the tool. It did not call a model, and it cannot submit an order."
)


@router.get("/tools", response_model=ToolCatalogueResponse)
def list_tools() -> ToolCatalogueResponse:
    """Return the local catalogue. The route does not call a model or write a row."""

    rows = catalogue()
    return ToolCatalogueResponse(
        source="local_catalogue",
        model="not_configured",
        chat="absent",
        tools=[ToolSpecResponse(name=row.name, effect=row.effect, executes=False) for row in rows],
        executed=False,
        invokes_model=False,
        execution_permitted=False,
        order_submitted=False,
        note=CATALOGUE_NOTE,
    )


@router.post("/tools/check", response_model=ToolCheckResponse)
def check_tool(body: ToolCheckRequest) -> ToolCheckResponse:
    """Judge one named call. The route does not run it."""

    try:
        decision = check_tool_call(tool_name=body.tool_name, arguments=body.arguments)
    except ToolInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ToolCheckResponse(
        tool_name=decision.tool_name,
        decision=decision.decision,
        reasons=list(decision.reasons),
        effect=decision.effect,
        executed=False,
        invokes_model=False,
        execution_permitted=False,
        order_submitted=False,
        note=CHECK_NOTE,
    )
