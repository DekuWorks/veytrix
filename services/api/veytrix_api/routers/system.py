"""Liveness, readiness, and a secret-free posture report."""

from __future__ import annotations

import platform

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from veytrix_api import __version__
from veytrix_api.db import get_db
from veytrix_api.models import AgentRow
from veytrix_api.schemas import (
    AGENT_CODES,
    DiagnosticsResponse,
    HealthResponse,
    ReadyResponse,
    SubmissionCondition,
    SubmissionEvidenceResponse,
    SystemStatusResponse,
    SystemStatusUnavailable,
    VersionInfo,
)
from veytrix_api.submission import (
    condition_results,
    confirm_phrase_matches,
    load_submission_config,
)

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/ready", response_model=ReadyResponse, responses={503: {"model": ReadyResponse}})
def ready(response: Response, db: Session = Depends(get_db)) -> ReadyResponse:
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        response.status_code = 503
        return ReadyResponse(status="unavailable", database="down")
    return ReadyResponse(status="ready", database="up")


@router.get(
    "/system/status",
    response_model=SystemStatusResponse | SystemStatusUnavailable,
    responses={503: {"model": SystemStatusUnavailable}},
)
def system_status(
    response: Response, db: Session = Depends(get_db)
) -> SystemStatusResponse | SystemStatusUnavailable:
    """Local posture plus a count of registry desks. No broker balance is included."""

    try:
        db.execute(text("SELECT 1"))
        rows = list(db.scalars(select(AgentRow)))
    except Exception:
        response.status_code = 503
        return SystemStatusUnavailable(status="unavailable", database="down")
    trading_capable = any(
        row.can_submit_orders
        or row.can_sign
        or row.can_transfer_funds
        or row.holds_credentials
        or not row.paper_only
        for row in rows
    )
    if trading_capable or {row.code for row in rows} != set(AGENT_CODES):
        raise HTTPException(status_code=503, detail="Agent registry is unavailable.")
    return SystemStatusResponse(
        status="ok",
        service="veytrix-api",
        env="local",
        trading_mode="paper",
        live_broker="disabled",
        auth="not_configured",
        database="up",
        execution_permitted=False,
        order_submitted=False,
        order_route="absent",
        agents_registered=len(rows),
        agents_can_trade=False,
        sample_data=True,
    )


SUBMISSION_NOTE = (
    "This process cannot pass --submit and does not read the broker account or the ledger "
    "kill switch. The confirmation phrase and the account number are not echoed. "
    "Not investment advice."
)


@router.get("/system/submission", response_model=SubmissionEvidenceResponse)
def submission_evidence() -> SubmissionEvidenceResponse:
    """Report the live gate. This route cannot turn a condition on or submit an order."""

    config = load_submission_config()
    conditions = [
        SubmissionCondition(name=name, met=met)
        for name, met in condition_results(config, confirm_matches=confirm_phrase_matches())
    ]
    return SubmissionEvidenceResponse(
        config_valid=config is not None,
        config_mode=config.mode if config else None,
        config_live_enabled=config.live_enabled if config else None,
        config_submit_orders=config.submit_orders if config else None,
        config_kill_switch=config.kill_switch if config else None,
        expected_account_set=bool(config.expected_account_number) if config else None,
        conditions=conditions,
        conditions_met=sum(item.met for item in conditions),
        account_status="not_read",
        ledger_kill_switch="not_read",
        submit_flag=False,
        api_reaches_engine=False,
        broker_called=False,
        paper_submission_from_api=False,
        live_submission_possible=False,
        expected_account_echoed=False,
        confirm_phrase_echoed=False,
        execution_permitted=False,
        order_submitted=False,
        order_route="absent",
        source="local_config",
        note=SUBMISSION_NOTE,
    )


@router.get("/diagnostics", response_model=DiagnosticsResponse)
def diagnostics() -> DiagnosticsResponse:
    return DiagnosticsResponse(
        service="veytrix-api",
        env="local",
        trading_mode="paper",
        live_broker="disabled",
        auth="not_configured",
        sample_data=True,
        execution_permitted=False,
        daily_weekly_stops_enforced=False,
        rate_limit="process_local",
        csrf="not_implemented",
        versions=VersionInfo(api=__version__, python=platform.python_version()),
    )
