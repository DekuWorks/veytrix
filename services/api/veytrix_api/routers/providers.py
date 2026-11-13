"""Read-only provider posture. This route does not call a model or a broker."""

from __future__ import annotations

from fastapi import APIRouter, Request

from veytrix_api.providers import ProviderPosture, build_posture
from veytrix_api.settings import Settings

router = APIRouter(prefix="/providers", tags=["providers"])


def _settings(request: Request) -> Settings:
    return request.app.state.settings


@router.get("/posture", response_model=ProviderPosture)
def provider_posture(request: Request) -> ProviderPosture:
    return build_posture(_settings(request))
