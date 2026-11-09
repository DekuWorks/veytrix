"""Local capital-reservation preview.

The result is a decision, not a row. Buying power is not read, nothing is
written, and there is no lock. A pass still cannot release an order. A second
call with the same inputs returns the same decision. A key that is already in
the outstanding list is not added again.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Literal

CENT = Decimal("0.01")
POLICY_VERSION = "local-2026-11-08"
BOOK_CAP = Decimal("100.00")
DESKS = (
    "SUPERVISOR-01",
    "DAY-01",
    "STOCK-01",
    "CRYPTO-01",
    "DEFI-01",
    "ETF-01",
    "FUTURES-01",
    "RESEARCH-01",
    "RISK-01",
    "TREASURY-01",
)
_REASON_ORDER = ("agent", "idempotency", "book")
_DECIMAL_TEXT = re.compile(r"^(?:0|[1-9]\d*)(?:\.\d+)?$")
_KEY = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


class ReservationInputError(ValueError):
    """The preview inputs are not a plain decimal figure or a desk key."""


@dataclass(frozen=True)
class ReservationPreview:
    """A hypothetical check. `release` cannot become an order from here."""

    policy_version: str
    rule_result: Literal["pass", "fail"]
    reasons: tuple[str, ...]
    requested: Decimal
    reserved_before: Decimal
    reserved_after: Decimal
    release: Literal["withheld"] = "withheld"
    persisted: Literal[False] = False
    lock: Literal["absent"] = "absent"
    buying_power_checked: Literal[False] = False
    broker_reconciled: Literal[False] = False
    execution_permitted: Literal[False] = False
    order_submitted: Literal[False] = False


def _as_decimal(value: object, name: str) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float) or not isinstance(value, (Decimal, str)):
        raise ReservationInputError(f"{name} must be a Decimal or a plain decimal string.")
    if isinstance(value, str):
        text = value.strip()
        if not _DECIMAL_TEXT.fullmatch(text):
            raise ReservationInputError(f"{name} must be a plain decimal string.")
        if len(text.replace(".", "")) > 40:
            raise ReservationInputError(f"{name} is too long.")
        parsed = Decimal(text)
    else:
        parsed = value
    if not parsed.is_finite():
        raise ReservationInputError(f"{name} must be finite.")
    return parsed


def _cents(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_EVEN)


def _key(value: object, name: str) -> str:
    if not isinstance(value, str) or _KEY.fullmatch(value) is None:
        raise ReservationInputError(f"{name} must be a lowercase idempotency key.")
    return value


def _desk(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise ReservationInputError(f"{name} must be a desk code.")
    return value


def preview_reservation(
    *,
    agent: str,
    notional: object,
    idempotency_key: str,
    outstanding: Sequence[Mapping[str, object]] = (),
) -> ReservationPreview:
    """Check one hypothetical reservation against a $100 book.

    Amounts are rounded to cents first. The book is the caller's outstanding
    list plus this request. An unknown desk, a key reused for a different
    amount or desk, a second key for a desk that already has a row, or a total
    above $100 fails. A matching key already in the list is not added again.
    Passing does not write a row and does not release an order.
    """

    if len(outstanding) > len(DESKS):
        raise ReservationInputError("outstanding holds at most one row per desk.")
    requested_agent = _desk(agent, "agent")
    key = _key(idempotency_key, "idempotency_key")
    requested = _cents(_as_decimal(notional, "notional"))
    if requested <= 0:
        raise ReservationInputError("notional must be positive.")

    seen_agents: set[str] = set()
    seen_keys: set[str] = set()
    rows: list[tuple[str, Decimal, str]] = []
    for row in outstanding:
        if set(row) != {"agent", "notional", "idempotency_key"}:
            raise ReservationInputError("outstanding row has the wrong fields.")
        row_agent = _desk(row["agent"], "outstanding agent")
        row_key = _key(row["idempotency_key"], "outstanding idempotency_key")
        row_notional = _cents(_as_decimal(row["notional"], "outstanding notional"))
        if row_notional <= 0:
            raise ReservationInputError("outstanding notional must be positive.")
        if row_agent not in DESKS:
            raise ReservationInputError("outstanding names an unknown desk.")
        if row_agent in seen_agents or row_key in seen_keys:
            raise ReservationInputError("outstanding lists a desk or a key twice.")
        seen_agents.add(row_agent)
        seen_keys.add(row_key)
        rows.append((row_agent, row_notional, row_key))

    reserved_before = _cents(sum((item[1] for item in rows), Decimal("0.00")))
    if reserved_before > BOOK_CAP:
        raise ReservationInputError("outstanding is already above the book cap.")

    matched_key = next((item for item in rows if item[2] == key), None)
    matched_agent = next((item for item in rows if item[0] == requested_agent), None)
    known = requested_agent in DESKS
    replay = (
        known
        and matched_key is not None
        and matched_key[0] == requested_agent
        and matched_key[1] == requested
    )
    reasons: list[str] = []
    if not known or (matched_agent is not None and matched_agent[2] != key):
        reasons.append("agent")
    key_mismatch = matched_key is not None and (
        matched_key[0] != requested_agent or matched_key[1] != requested
    )
    if key_mismatch:
        reasons.append("idempotency")
    projected = reserved_before if replay else _cents(reserved_before + requested)
    if not replay and projected > BOOK_CAP:
        reasons.append("book")
    ordered = tuple(reason for reason in _REASON_ORDER if reason in reasons)
    return ReservationPreview(
        policy_version=POLICY_VERSION,
        rule_result="fail" if ordered else "pass",
        reasons=ordered,
        requested=requested,
        reserved_before=reserved_before,
        reserved_after=reserved_before if ordered else projected,
    )
