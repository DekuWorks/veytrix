"""Webhook intake. Disabled by default. The handler never calls a broker."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException

from veytrix_api.comms.envelope import Safety
from veytrix_api.signals import ingest

router = APIRouter(prefix="/signals", tags=["signals"])


class SignalResult(Safety):
    provider: str
    outcome: str
    detail: str
    broker_called: Literal["false"] = "false"


@router.post("/{provider}", response_model=SignalResult)
def receive(
    provider: str,
    payload: dict,
    strategy: str = "unset",
    account: str = "unset",
) -> SignalResult:
    if provider not in {"traderspost", "signalstack"}:
        raise HTTPException(status_code=404, detail="Unknown signal provider.")
    decision = ingest(provider, payload, strategy=strategy, account=account)  # type: ignore[arg-type]
    return SignalResult(
        provider=decision["provider"],
        outcome=decision["outcome"],
        detail=decision["detail"],
    )
