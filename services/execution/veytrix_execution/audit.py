"""In-memory audit rows for paper recorders.

Rows live in the process. They are not the API audit tables, not broker fills,
and not written to Postgres by this package.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Literal

SECRET_KEYS = frozenset(
    {
        "password",
        "secret",
        "token",
        "api_key",
        "apikey",
        "authorization",
        "api-key",
        "secret_key",
        "access_token",
        "refresh_token",
    }
)


def redact(value: object, depth: int = 0) -> object:
    if depth > 32:
        return {"truncated": True}
    if isinstance(value, dict):
        cleaned: dict[str, object] = {}
        for key, item in value.items():
            name = str(key)
            folded = name.lower().replace("-", "_")
            if folded in SECRET_KEYS or name.lower() in SECRET_KEYS:
                cleaned[name] = "[redacted]"
            else:
                cleaned[name] = redact(item, depth + 1)
        return cleaned
    if isinstance(value, list):
        return [redact(item, depth + 1) for item in value[:32]]
    if isinstance(value, str):
        return value
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return str(value)[:200]


def new_audit_id(seed: str, nonce: int) -> str:
    digest = hashlib.sha256(f"{nonce}:{seed}".encode()).hexdigest()[:16]
    return f"audit-{digest}"


@dataclass
class AuditRow:
    audit_id: str
    route: str
    strategy_id: str
    account_ref: str
    mode: Literal["paper"]
    signal: dict[str, object]
    response: dict[str, object]
    rejection_reason: str
    recording_enabled: bool
    retry_count: int = 0
    timed_out: bool = False
    broker_outcome: Literal["rejected"] = "rejected"
    forwarded: Literal[False] = False
    execution_permitted: Literal[False] = False
    order_submitted: Literal[False] = False


@dataclass
class AuditLog:
    rows: list[AuditRow] = field(default_factory=list)
    _index: dict[tuple[str, str, str, str], AuditRow] = field(default_factory=dict)

    def find(self, key: tuple[str, str, str, str]) -> AuditRow | None:
        return self._index.get(key)

    def append(self, key: tuple[str, str, str, str], row: AuditRow) -> AuditRow:
        self.rows.append(row)
        self._index[key] = row
        return row


def response(
    message_code: str,
    message: str,
    *,
    audit_id: str | None,
    retry_count: int = 0,
    duplicate: bool = False,
) -> dict[str, object]:
    return {
        "success": False,
        "messageCode": message_code,
        "message": message,
        "mode": "paper",
        "quote": None,
        "sender_fields_are_not_prices": True,
        "broker_outcome": "rejected",
        "forwarded": False,
        "execution_permitted": False,
        "order_submitted": False,
        "audit_id": audit_id,
        "duplicate": duplicate,
        "retry_count": retry_count,
    }


def format_audit_log(row: AuditRow) -> str:
    """Operator line. The signal body is omitted so a sender price is not logged as a quote."""

    return (
        "mode=paper "
        f"route={row.route} "
        f"strategy={row.strategy_id} "
        f"account_ref={row.account_ref} "
        "broker_outcome=rejected "
        "forwarded=false "
        "execution_permitted=false "
        "order_submitted=false "
        f"reason={row.rejection_reason} "
        f"audit_id={row.audit_id}"
    )


@dataclass(frozen=True)
class Validation:
    ok: bool
    message_code: str
    message: str
    signal: dict[str, object]
    store: bool = True


@dataclass(frozen=True)
class Receipt:
    stored: bool
    duplicate: bool
    response_body: dict[str, object]
    row: AuditRow | None = None

    @property
    def broker_outcome(self) -> Literal["rejected"]:
        return "rejected"

    @property
    def forwarded(self) -> Literal[False]:
        return False

    @property
    def execution_permitted(self) -> Literal[False]:
        return False

    @property
    def order_submitted(self) -> Literal[False]:
        return False
