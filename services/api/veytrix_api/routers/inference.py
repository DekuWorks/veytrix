"""Model routing posture. This route does not call a model or place an order."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from veytrix_api.model_router import PERSONAS, RouteDecision, route_task
from veytrix_api.settings import Settings

router = APIRouter(prefix="/inference", tags=["inference"])


class InferencePosture(BaseModel):
    cursor_subscription_runs_agents: bool = False
    paid_inference_enabled: bool
    monthly_ceiling_usd: Decimal
    spent_usd: Decimal
    ollama_configured: bool
    personas: dict[str, str]
    execution_permitted: bool = False
    order_submitted: bool = False
    auto_purchase: bool = False


class InferenceRequest(BaseModel):
    agent_code: str = Field(min_length=1, max_length=32)
    task: str = Field(min_length=1, max_length=64)
    provider: str = Field(default="none", min_length=1, max_length=32)


class InferenceResponse(BaseModel):
    agent_code: str
    persona: str
    task: str
    provider: str
    allowed: bool
    reason: str
    estimated_usd: Decimal
    paid: bool
    execution_permitted: bool = False
    order_submitted: bool = False


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _decide(request: Request, body: InferenceRequest) -> RouteDecision:
    settings = _settings(request)
    return route_task(
        agent_code=body.agent_code,
        task=body.task,
        provider=body.provider,
        paid_inference_enabled=settings.paid_inference_enabled,
        monthly_ceiling_usd=settings.ai_monthly_ceiling_usd,
        spent_usd=Decimal("0"),
        ollama_configured=bool(settings.ollama_url),
    )


@router.get("/posture", response_model=InferencePosture)
def inference_posture(request: Request) -> InferencePosture:
    settings = _settings(request)
    return InferencePosture(
        paid_inference_enabled=settings.paid_inference_enabled,
        monthly_ceiling_usd=settings.ai_monthly_ceiling_usd,
        spent_usd=Decimal("0"),
        ollama_configured=bool(settings.ollama_url),
        personas=dict(PERSONAS),
    )


@router.post("/route", response_model=InferenceResponse)
def inference_route(body: InferenceRequest, request: Request) -> InferenceResponse:
    decision = _decide(request, body)
    return InferenceResponse(
        agent_code=decision.agent_code,
        persona=decision.persona,
        task=decision.task,
        provider=decision.provider,
        allowed=decision.allowed,
        reason=decision.reason,
        estimated_usd=decision.estimated_usd,
        paid=decision.paid,
    )
