"""Disabled paper webhook adapters. They record a decision and never call a broker.

TraderPost and SignalStack stay separate. One strategy and account can select
one route, and the default route is none. A selected route still rejects the
broker step. Official integration for TraderPost is a webhook, not a trading API:
https://docs.traderspost.io/docs/additional-information/faq
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from veytrix_api.models import SignalAuditRow

Provider = Literal["traderspost", "signalstack"]
Outcome = Literal[
    "rejected_disabled",
    "rejected_route",
    "rejected_payload",
    "rejected_duplicate",
    "rejected_timeout",
    "rejected_broker",
]

adapters_enabled = False
_routes: dict[tuple[str, str], str] = {}
_seen: set[str] = set()
TIMEOUT = timedelta(seconds=30)


def reset() -> None:
    """Test helper. Production starts disabled with no selected route."""

    global adapters_enabled
    adapters_enabled = False
    _routes.clear()
    _seen.clear()


def set_route(strategy: str, account: str, route: str) -> str:
    """Select one execution route. `none` clears it. Two providers cannot both be selected."""

    if route not in {"none", "traderspost", "signalstack"}:
        raise ValueError("Unknown execution route.")
    _routes[(strategy, account)] = route
    return route


def _fingerprint(provider: str, payload: dict) -> str:
    body = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(f"{provider}:{body}".encode()).hexdigest()


def _parse(provider: str, payload: object) -> str | None:
    if not isinstance(payload, dict):
        return "payload"
    if provider == "traderspost":
        ticker = payload.get("ticker")
        action = payload.get("action")
        quantity = payload.get("quantity")
        if not isinstance(ticker, str) or not ticker.strip():
            return "ticker"
        if action not in {"buy", "sell"}:
            return "action"
        if isinstance(quantity, bool) or not isinstance(quantity, (int, float)) or quantity <= 0:
            return "quantity"
        return None
    symbol = payload.get("symbol")
    side = payload.get("side")
    qty = payload.get("qty")
    if not isinstance(symbol, str) or not symbol.strip():
        return "symbol"
    if side not in {"buy", "sell"}:
        return "side"
    if isinstance(qty, bool) or not isinstance(qty, (int, float)) or qty <= 0:
        return "qty"
    return None


def _stale(payload: dict, now: datetime) -> bool:
    raw = payload.get("sent_at")
    if not isinstance(raw, str):
        return False
    try:
        sent = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return True
    if sent.tzinfo is None:
        sent = sent.replace(tzinfo=UTC)
    return now - sent > TIMEOUT


def ingest(
    provider: Provider,
    payload: object,
    *,
    strategy: str,
    account: str,
    now: datetime | None = None,
    db: Session | None = None,
) -> dict[str, str]:
    """Validate one webhook and reject it. The return value is the audit row."""

    moment = now or datetime.now(UTC)
    body = payload if isinstance(payload, dict) else {"invalid": True}
    fingerprint = _fingerprint(provider, body)
    selected = _routes.get((strategy, account), "none")
    if not adapters_enabled:
        outcome: Outcome = "rejected_disabled"
        detail = "adapter_disabled"
    elif selected != provider:
        outcome = "rejected_route"
        detail = f"selected_{selected}"
    elif fingerprint in _seen:
        outcome = "rejected_duplicate"
        detail = "duplicate_signal"
    else:
        problem = _parse(provider, payload)
        if problem is not None:
            outcome = "rejected_payload"
            detail = problem
        elif isinstance(payload, dict) and _stale(payload, moment):
            outcome = "rejected_timeout"
            detail = "stale_signal"
        else:
            outcome = "rejected_broker"
            detail = "paper_broker_disabled"
            _seen.add(fingerprint)
    if db is not None:
        _store(db, provider, outcome, fingerprint, detail)
    return {
        "provider": provider,
        "outcome": outcome,
        "fingerprint": fingerprint,
        "detail": detail,
        "broker_called": "false",
    }


def _store(db: Session, provider: str, outcome: str, fingerprint: str, detail: str) -> None:
    row = SignalAuditRow(
        id=uuid.uuid4(),
        provider=provider,
        outcome=outcome,
        fingerprint=fingerprint,
        detail=detail[:200],
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        return
