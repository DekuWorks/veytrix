"""Local order preview for the $100 AAPL rules.

The result is a decision, not an order. Buying power is not read, nothing is
reserved, and release stays withheld even when every local rule passes. A
second call with the same inputs returns the same decision.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Literal

CENT = Decimal("0.01")
POLICY_VERSION = "local-2026-11-08"
ALLOWED_SYMBOL = "AAPL"
MAX_NOTIONAL = Decimal("100.00")
MAX_POSITION_NOTIONAL = Decimal("100.00")
MAX_ORDERS_PER_DAY = 2
QUOTE_MAX_AGE_SECONDS = 120
CASH_LEVERAGE = Decimal("1")
_REASON_ORDER = (
    "short",
    "leverage",
    "symbol",
    "stale",
    "notional",
    "position",
    "daily_orders",
)
_DECIMAL_TEXT = re.compile(r"^(?:0|[1-9]\d*)(?:\.\d+)?$")


class ShieldInputError(ValueError):
    """The preview inputs are not a plain decimal figure."""


@dataclass(frozen=True)
class ShieldPreview:
    """A hypothetical check. `release` cannot become an order from here."""

    policy_version: str
    rule_result: Literal["pass", "fail"]
    reasons: tuple[str, ...]
    notional: Decimal
    position_after: Decimal
    release: Literal["withheld"] = "withheld"
    buying_power_checked: Literal[False] = False
    owner_approved: Literal[False] = False
    execution_permitted: Literal[False] = False
    order_submitted: Literal[False] = False


def _as_decimal(value: object, name: str) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float) or not isinstance(value, (Decimal, str)):
        raise ShieldInputError(f"{name} must be a Decimal or a plain decimal string.")
    if isinstance(value, str):
        text = value.strip()
        if not _DECIMAL_TEXT.fullmatch(text):
            raise ShieldInputError(f"{name} must be a plain decimal string.")
        if len(text.replace(".", "")) > 40:
            raise ShieldInputError(f"{name} is too long.")
        parsed = Decimal(text)
    else:
        parsed = value
    if not parsed.is_finite():
        raise ShieldInputError(f"{name} must be finite.")
    return parsed


def _cents(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_EVEN)


def preview_order(
    *,
    symbol: str,
    side: str,
    limit_price: object,
    quantity: object,
    position_notional: object,
    orders_today: int,
    quote_age_seconds: int,
    leverage: object,
) -> ShieldPreview:
    """Check one hypothetical buy against the local caps.

    Price, quantity, and the current position are rounded to cents before the
    comparison. A short, a leveraged figure, a symbol other than AAPL, a quote
    older than 120 seconds, a notional above $100, a position that would finish
    above $100, or a third order today fails the rule. Passing the rule does
    not release an order.
    """

    if side not in {"long", "short"}:
        raise ShieldInputError("side must be long or short.")
    if isinstance(orders_today, bool) or not isinstance(orders_today, int) or orders_today < 0:
        raise ShieldInputError("orders_today must be a non-negative integer.")
    if (
        isinstance(quote_age_seconds, bool)
        or not isinstance(quote_age_seconds, int)
        or quote_age_seconds < 0
    ):
        raise ShieldInputError("quote_age_seconds must be a non-negative integer.")
    price = _cents(_as_decimal(limit_price, "limit_price"))
    shares = _cents(_as_decimal(quantity, "quantity"))
    held = _cents(_as_decimal(position_notional, "position_notional"))
    borrowed = _cents(_as_decimal(leverage, "leverage"))
    if price <= 0 or shares <= 0 or held < 0 or borrowed <= 0:
        raise ShieldInputError(
            "price and quantity must be positive, and position cannot be negative."
        )
    notional = _cents(price * shares)
    position_after = _cents(held + notional)
    reasons: list[str] = []
    if side == "short":
        reasons.append("short")
    if borrowed != CASH_LEVERAGE:
        reasons.append("leverage")
    if symbol != ALLOWED_SYMBOL:
        reasons.append("symbol")
    if quote_age_seconds > QUOTE_MAX_AGE_SECONDS:
        reasons.append("stale")
    if notional > MAX_NOTIONAL:
        reasons.append("notional")
    if position_after > MAX_POSITION_NOTIONAL:
        reasons.append("position")
    if orders_today >= MAX_ORDERS_PER_DAY:
        reasons.append("daily_orders")
    ordered = tuple(reason for reason in _REASON_ORDER if reason in reasons)
    return ShieldPreview(
        policy_version=POLICY_VERSION,
        rule_result="fail" if ordered else "pass",
        reasons=ordered,
        notional=notional,
        position_after=position_after,
    )
