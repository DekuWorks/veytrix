"""Read-only FUTURES-01 posture. This route does not call a broker."""

from __future__ import annotations

from fastapi import APIRouter

from veytrix_api.schemas import FuturesPostureResponse

router = APIRouter(prefix="/futures", tags=["futures"])

POSTURE_NOTE = (
    "FUTURES-01 is disabled. Topstep automation is off and no account is connected. "
    "MES and MNQ are labels only. This API does not submit an order."
)


@router.get("/posture", response_model=FuturesPostureResponse)
def posture() -> FuturesPostureResponse:
    """State that the futures desk cannot trade. No market-data or broker call."""

    return FuturesPostureResponse(
        desk="FUTURES-01",
        status="disabled",
        symbols=["MES", "MNQ"],
        topstep_automation="disabled",
        topstep_account="not_connected",
        orders="absent",
        market_data="not_read",
        can_enable=False,
        execution_permitted=False,
        order_submitted=False,
        broker_called=False,
        source="local_posture",
        note=POSTURE_NOTE,
    )
