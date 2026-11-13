"""Paper execution boundary.

One route can be selected for a strategy and for an account label. The default
is none, and recording is off. A selected route still rejects the broker: this
process has no broker client and no HTTP client.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, cast

from veytrix_execution.audit import (
    AuditLog,
    AuditRow,
    Receipt,
    format_audit_log,
    new_audit_id,
    response,
)
from veytrix_execution.limits import ID_PATTERN, KEY_PATTERN, TIMEOUT_SECONDS
from veytrix_execution.signalstack import validate_signalstack
from veytrix_execution.traderspost import validate_traderspost
from veytrix_execution.tradingview import validate_tradingview

RouteName = Literal["none", "tradingview_recorder", "traderspost", "signalstack"]
ROUTES = ("none", "tradingview_recorder", "traderspost", "signalstack")
BROKER_ROUTES = frozenset({"traderspost", "signalstack"})
LIVE_NAMES = ("VEYTRIX_ENABLE_LIVE_BROKER", "ALPACA_LIVE_TRADE", "MAC01_LIVE_CONFIRM")
_OFF = frozenset({"", "0", "false", "no", "off"})
_ID = re.compile(ID_PATTERN)
_KEY = re.compile(KEY_PATTERN)

VALIDATORS = {
    "tradingview_recorder": validate_tradingview,
    "traderspost": validate_traderspost,
    "signalstack": validate_signalstack,
}


class BoundaryError(ValueError):
    """The caller asked for a route the boundary will not store."""


class RouteConflict(BoundaryError):
    """The strategy or account already has a selected route."""


def live_variable_names(environ: Mapping[str, str]) -> tuple[str, ...]:
    """Return names that are set to a live-trading value. Values are discarded."""

    found: list[str] = []
    for name in LIVE_NAMES:
        if name in environ and environ[name].strip().lower() not in _OFF:
            found.append(name)
    return tuple(found)


@dataclass
class PaperBoundary:
    recording_enabled: bool = False
    live_blocked: bool = False
    live_names: tuple[str, ...] = ()
    timeout_seconds: float = TIMEOUT_SECONDS
    mode: Literal["paper"] = "paper"
    audit: AuditLog = field(default_factory=AuditLog)
    selections: dict[tuple[str, str], RouteName] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.mode != "paper":
            raise BoundaryError("This boundary is paper-only.")
        self.mode = "paper"

    @classmethod
    def from_mapping(cls, environ: Mapping[str, str]) -> PaperBoundary:
        names = live_variable_names(environ)
        return cls(live_blocked=bool(names), live_names=names)

    @classmethod
    def from_process_environ(cls) -> PaperBoundary:
        picked = {name: os.environ[name] for name in LIVE_NAMES if name in os.environ}
        return cls.from_mapping(picked)

    def selected(self, strategy_id: str, account_ref: str) -> RouteName:
        return self.selections.get((strategy_id, account_ref), "none")

    def select(
        self,
        strategy_id: str,
        account_ref: str,
        route: str,
        *,
        replace: bool = False,
    ) -> RouteName:
        self._check_label(strategy_id, "strategy_id")
        self._check_label(account_ref, "account_ref")
        if route not in ROUTES:
            raise BoundaryError(
                "Unknown route. Choices are none, tradingview_recorder, traderspost, signalstack."
            )
        chosen = cast(RouteName, route)
        key = (strategy_id, account_ref)
        current = self.selections.get(key, "none")
        if chosen != "none" and current not in {"none", chosen} and not replace:
            raise RouteConflict(
                f"{strategy_id}/{account_ref} already uses {current}. "
                "Pass replace=True to switch that pair, which drops the previous route."
            )
        if chosen != "none":
            conflict = self._shared_conflict(strategy_id, account_ref, chosen)
            if conflict is not None:
                raise RouteConflict(conflict)
        if chosen == "none":
            self.selections.pop(key, None)
            return "none"
        self.selections[key] = chosen
        return chosen

    def enable_recording(self) -> None:
        if self.live_blocked:
            names = ", ".join(self.live_names) or "a live-trading variable"
            raise BoundaryError(f"Recording stays off because {names} is set.")
        self.recording_enabled = True

    def ingest(
        self,
        *,
        route: str,
        strategy_id: str,
        account_ref: str,
        idempotency_key: str,
        payload: object,
        content_type: str | None,
        started_at: datetime,
        now: datetime,
        retry: bool = False,
    ) -> Receipt:
        self._check_label(strategy_id, "strategy_id")
        self._check_label(account_ref, "account_ref")
        if _KEY.fullmatch(idempotency_key) is None:
            raise BoundaryError(
                "idempotency_key must be 1 to 128 characters of letters, numbers, and .:_-"
            )
        if route not in VALIDATORS:
            raise BoundaryError("ingest needs a recorder route, not none.")
        key = (strategy_id, account_ref, route, idempotency_key)
        existing = self.audit.find(key)
        if existing is not None:
            if retry:
                existing.retry_count += 1
                existing.response["retry_count"] = existing.retry_count
                return Receipt(True, False, dict(existing.response), existing)
            body = dict(existing.response)
            body["duplicate"] = True
            body["messageCode"] = "duplicate"
            body["message"] = (
                "This idempotency key was already recorded. No second row was written."
            )
            return Receipt(False, True, body, existing)

        if self.live_blocked:
            return self._store(
                key,
                route=route,
                strategy_id=strategy_id,
                account_ref=account_ref,
                code="live-environment-refused",
                message="A live-trading variable is set. Nothing was forwarded.",
                signal={"omitted": "live_environment"},
                timed_out=False,
            )
        if _expired(started_at, now, self.timeout_seconds):
            return self._store(
                key,
                route=route,
                strategy_id=strategy_id,
                account_ref=account_ref,
                code="timeout",
                message=f"The paper recorder budget is {self.timeout_seconds:.0f} seconds.",
                signal={"omitted": "timeout_before_validation"},
                timed_out=True,
            )

        validator = VALIDATORS[route]
        result = validator(payload, content_type)
        if not result.store:
            body = response(result.message_code, result.message, audit_id=None)
            return Receipt(False, False, body, None)
        if not result.ok:
            return self._store(
                key,
                route=route,
                strategy_id=strategy_id,
                account_ref=account_ref,
                code=result.message_code,
                message=result.message,
                signal=result.signal,
                timed_out=False,
            )
        if not self.recording_enabled or self.selected(strategy_id, account_ref) != route:
            return self._store(
                key,
                route=route,
                strategy_id=strategy_id,
                account_ref=account_ref,
                code="route-disabled",
                message="Recording is off or this route is not the selected route.",
                signal=result.signal,
                timed_out=False,
            )
        return self._store(
            key,
            route=route,
            strategy_id=strategy_id,
            account_ref=account_ref,
            code=result.message_code,
            message=result.message,
            signal=result.signal,
            timed_out=False,
        )

    def log_line(self, row: AuditRow) -> str:
        return format_audit_log(row)

    def _store(
        self,
        key: tuple[str, str, str, str],
        *,
        route: str,
        strategy_id: str,
        account_ref: str,
        code: str,
        message: str,
        signal: dict[str, object],
        timed_out: bool,
    ) -> Receipt:
        audit_id = new_audit_id(":".join(key), len(self.audit.rows) + 1)
        body = response(code, message, audit_id=audit_id)
        row = AuditRow(
            audit_id=audit_id,
            route=route,
            strategy_id=strategy_id,
            account_ref=account_ref,
            mode="paper",
            signal=signal,
            response=body,
            rejection_reason=code,
            recording_enabled=self.recording_enabled,
            timed_out=timed_out,
        )
        self.audit.append(key, row)
        return Receipt(True, False, body, row)

    def _shared_conflict(self, strategy_id: str, account_ref: str, route: str) -> str | None:
        key = (strategy_id, account_ref)
        for (strategy, account), selected in self.selections.items():
            if (strategy, account) == key or selected == "none":
                continue
            shares = strategy == strategy_id or account == account_ref
            if not shares:
                continue
            if selected in BROKER_ROUTES or route in BROKER_ROUTES:
                return (
                    f"{strategy}/{account} already uses {selected}. "
                    "TradersPost and SignalStack cannot share a strategy or an account label."
                )
            return (
                f"{strategy}/{account} already uses {selected}. "
                "One route is allowed for a strategy and for an account label."
            )
        return None

    @staticmethod
    def _check_label(value: str, field_name: str) -> None:
        if _ID.fullmatch(value) is None:
            raise BoundaryError(f"{field_name} must be a short lowercase label, not a credential.")


def _expired(started_at: datetime, now: datetime, timeout_seconds: float) -> bool:
    if started_at.tzinfo is None or now.tzinfo is None:
        raise BoundaryError("started_at and now must be timezone-aware.")
    elapsed = (now - started_at).total_seconds()
    return elapsed < 0 or elapsed > timeout_seconds
