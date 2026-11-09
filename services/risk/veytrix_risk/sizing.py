"""Experimental long-only paper position sizing.

Share count uses decimal arithmetic:

    shares = floor(min(
        account equity * risk fraction / stop distance,
        account equity * max allocation / entry price,
    ))

Stop distance for a long position is entry price minus stop price.
Daily and weekly loss stops are stored on the policy and are not applied
here, because this package has no ledger. A result is a research figure.
It is not an order and it is not a promise that a stop will fill.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal
from typing import Literal

ABSOLUTE_RISK_FRACTION_CEILING = Decimal("0.02")
ABSOLUTE_MAX_ALLOCATION_FRACTION = Decimal("0.10")
STOPS_NOT_ENFORCED = (
    "Daily and weekly stops are stored as policy and are not enforced against a ledger yet. "
    "Position sizing is experimental. Stops can fail."
)
_DECIMAL_TEXT = re.compile(r"^(?:0|[1-9]\d*)(?:\.\d+)?$")
BindingConstraint = Literal["risk", "allocation", "both", "none"]


class SizingError(ValueError):
    """The inputs cannot be sized inside the paper policy."""


class PolicyError(ValueError):
    """A policy object breaks a hard safety check."""


def _as_decimal(value: Decimal | str, name: str) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float) or not isinstance(value, (Decimal, str)):
        raise SizingError(f"{name} must be a Decimal or a plain decimal string.")
    if isinstance(value, str):
        text = value.strip()
        if not _DECIMAL_TEXT.fullmatch(text):
            raise SizingError(f"{name} must be a plain decimal string such as 100.00.")
        if len(text.replace(".", "")) > 40:
            raise SizingError(f"{name} is too long.")
        parsed = Decimal(text)
    else:
        parsed = value
    if not parsed.is_finite():
        raise SizingError(f"{name} must be finite.")
    return parsed


@dataclass(frozen=True)
class RiskPolicy:
    """Configurable experimental paper policy.

    The absolute risk ceiling stays 0.02 even if a caller tries to raise it.
    """

    name: str
    per_trade_risk_fraction: Decimal
    daily_loss_stop_fraction: Decimal
    weekly_loss_stop_fraction: Decimal
    max_allocation_fraction: Decimal
    risk_fraction_ceiling: Decimal = ABSOLUTE_RISK_FRACTION_CEILING
    daily_stop_enforced: bool = False
    weekly_stop_enforced: bool = False
    experimental: bool = True
    trading_mode: str = "paper"

    def __post_init__(self) -> None:
        if self.trading_mode != "paper":
            raise PolicyError("Only a paper policy is allowed.")
        if not self.experimental:
            raise PolicyError("The policy must stay marked experimental.")
        if self.daily_stop_enforced or self.weekly_stop_enforced:
            raise PolicyError("Daily and weekly stops are not enforced against a ledger.")
        if self.risk_fraction_ceiling != ABSOLUTE_RISK_FRACTION_CEILING:
            raise PolicyError("The absolute risk ceiling cannot be changed.")
        for field_name in (
            "per_trade_risk_fraction",
            "daily_loss_stop_fraction",
            "weekly_loss_stop_fraction",
            "max_allocation_fraction",
            "risk_fraction_ceiling",
        ):
            value = getattr(self, field_name)
            if isinstance(value, float) or not isinstance(value, Decimal):
                raise PolicyError(f"{field_name} must be Decimal.")
            if not value.is_finite() or value <= 0:
                raise PolicyError(f"{field_name} must be a positive finite Decimal.")
        if self.per_trade_risk_fraction > self.risk_fraction_ceiling:
            raise PolicyError("Per-trade risk exceeds the absolute ceiling of 0.02.")
        if self.daily_loss_stop_fraction > ABSOLUTE_RISK_FRACTION_CEILING:
            raise PolicyError("Daily stop fraction exceeds 0.02.")
        if self.weekly_loss_stop_fraction > Decimal("0.05"):
            raise PolicyError("Weekly stop fraction exceeds 0.05.")
        if self.max_allocation_fraction > ABSOLUTE_MAX_ALLOCATION_FRACTION:
            raise PolicyError("Max allocation exceeds 0.10.")


DEFAULT_POLICY = RiskPolicy(
    name="experimental-paper-default",
    per_trade_risk_fraction=Decimal("0.005"),
    daily_loss_stop_fraction=Decimal("0.01"),
    weekly_loss_stop_fraction=Decimal("0.03"),
    max_allocation_fraction=Decimal("0.10"),
)


@dataclass(frozen=True)
class SizingResult:
    shares: int
    binding_constraint: BindingConstraint
    stop_distance: Decimal
    planned_risk_amount: Decimal
    risk_budget: Decimal
    notional: Decimal
    account_equity: Decimal
    entry_price: Decimal
    stop_price: Decimal
    risk_fraction: Decimal
    max_allocation_fraction: Decimal
    daily_loss_stop_fraction: Decimal
    weekly_loss_stop_fraction: Decimal
    policy_name: str
    warning: str | None
    note: str = STOPS_NOT_ENFORCED
    execution_permitted: bool = False
    order_submitted: bool = False
    daily_stop_enforced: bool = False
    weekly_stop_enforced: bool = False

    def __post_init__(self) -> None:
        if self.execution_permitted or self.order_submitted:
            raise SizingError("Sizing cannot permit execution or submit an order.")
        if self.daily_stop_enforced or self.weekly_stop_enforced:
            raise SizingError("Daily and weekly stops are not enforced.")
        if self.note != STOPS_NOT_ENFORCED:
            raise SizingError("The stops warning cannot be replaced.")


def size_position(
    account_equity: Decimal | str,
    entry_price: Decimal | str,
    stop_price: Decimal | str,
    *,
    side: str = "long",
    risk_fraction: Decimal | str | None = None,
    max_allocation_fraction: Decimal | str | None = None,
    policy: RiskPolicy = DEFAULT_POLICY,
) -> SizingResult:
    """Calculate a long-only paper share count. This function does not place an order."""

    if side != "long":
        raise SizingError("Only long positions are allowed. Shorting is not permitted.")

    equity = _as_decimal(account_equity, "account_equity")
    entry = _as_decimal(entry_price, "entry_price")
    stop = _as_decimal(stop_price, "stop_price")
    if equity <= 0:
        raise SizingError("Account equity must be positive.")
    if entry <= 0:
        raise SizingError("Entry price must be positive.")
    if stop <= 0:
        raise SizingError("Stop price must be positive.")
    if stop >= entry:
        raise SizingError("For a long position the stop price must be below the entry price.")

    effective_risk = (
        policy.per_trade_risk_fraction
        if risk_fraction is None
        else _as_decimal(risk_fraction, "risk_fraction")
    )
    effective_allocation = (
        policy.max_allocation_fraction
        if max_allocation_fraction is None
        else _as_decimal(max_allocation_fraction, "max_allocation_fraction")
    )
    if effective_risk <= 0:
        raise SizingError("Risk fraction must be positive.")
    if effective_risk > ABSOLUTE_RISK_FRACTION_CEILING:
        raise SizingError("Risk fraction exceeds the absolute ceiling of 0.02.")
    if effective_risk > policy.per_trade_risk_fraction:
        raise SizingError("Risk fraction exceeds the configured paper policy.")
    if effective_allocation <= 0:
        raise SizingError("Max allocation must be positive.")
    if effective_allocation > policy.max_allocation_fraction:
        raise SizingError("Max allocation exceeds the configured paper policy.")
    if effective_allocation > ABSOLUTE_MAX_ALLOCATION_FRACTION:
        raise SizingError("Max allocation exceeds the absolute ceiling of 0.10.")

    stop_distance = entry - stop
    risk_budget = equity * effective_risk
    shares_by_risk = risk_budget / stop_distance
    shares_by_allocation = (equity * effective_allocation) / entry
    shares = int(min(shares_by_risk, shares_by_allocation).to_integral_value(rounding=ROUND_FLOOR))
    if shares == 0:
        binding: BindingConstraint = "none"
    elif shares_by_risk == shares_by_allocation:
        binding = "both"
    elif shares_by_risk < shares_by_allocation:
        binding = "risk"
    else:
        binding = "allocation"

    warning = None
    if shares == 0:
        warning = "The inputs round down to zero shares. No order was submitted."

    return SizingResult(
        shares=shares,
        binding_constraint=binding,
        stop_distance=stop_distance,
        planned_risk_amount=Decimal(shares) * stop_distance,
        risk_budget=risk_budget,
        notional=Decimal(shares) * entry,
        account_equity=equity,
        entry_price=entry,
        stop_price=stop,
        risk_fraction=effective_risk,
        max_allocation_fraction=effective_allocation,
        daily_loss_stop_fraction=policy.daily_loss_stop_fraction,
        weekly_loss_stop_fraction=policy.weekly_loss_stop_fraction,
        policy_name=policy.name,
        warning=warning,
    )
