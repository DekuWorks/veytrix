"""Request dependencies. The size route reads a policy; it does not write an order."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from veytrix_api.db import get_db
from veytrix_api.models import RiskPolicyRow
from veytrix_risk.sizing import PolicyError, RiskPolicy


def get_policy(request: Request, db: Session = Depends(get_db)) -> RiskPolicy:
    del request
    try:
        rows = list(db.scalars(select(RiskPolicyRow)))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Risk policy store is unavailable.") from exc
    if len(rows) != 1:
        raise HTTPException(
            status_code=503,
            detail="Expected exactly one experimental paper policy.",
        )
    try:
        return rows[0].to_domain()
    except PolicyError as exc:
        raise HTTPException(
            status_code=503,
            detail="Stored risk policy failed safety checks.",
        ) from exc
