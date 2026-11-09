"""Local monthly distribution projection.

This is decimal arithmetic on figures the caller already has. It does not
read a broker, store a payout, or move money. A second call with the same
inputs returns the same projection. The $2,000 cap is the plan's monthly
maximum, not an authorisation to pay it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_EVEN, Decimal

CENT = Decimal("0.01")
DISTRIBUTION_FRACTION = Decimal("0.50")
DISTRIBUTION_CAP = Decimal("2000.00")
REVIEW_DAY = 5
_DECIMAL_TEXT = re.compile(r"^-?(?:0|[1-9]\d*)(?:\.\d+)?$")


class TreasuryInputError(ValueError):
    """The projection inputs are not a plain money figure."""


@dataclass(frozen=True)
class MonthProjection:
    """One month's proposal. Nothing here is settled or transferred."""

    realised_profit: Decimal
    costs: Decimal
    loss_carryforward: Decimal
    eligible_profit: Decimal
    proposed_distribution: Decimal
    retained: Decimal
    loss_carryforward_out: Decimal


def _as_decimal(value: object, name: str) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float) or not isinstance(value, (Decimal, str)):
        raise TreasuryInputError(f"{name} must be a Decimal or a plain decimal string.")
    if isinstance(value, str):
        text = value.strip()
        if not _DECIMAL_TEXT.fullmatch(text):
            raise TreasuryInputError(f"{name} must be a plain decimal string.")
        if len(text.replace(".", "").replace("-", "")) > 40:
            raise TreasuryInputError(f"{name} is too long.")
        parsed = Decimal(text)
    else:
        parsed = value
    if not parsed.is_finite():
        raise TreasuryInputError(f"{name} must be finite.")
    return parsed


def _cents(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_EVEN)


def project_month(
    *,
    realised_profit: object,
    costs: object,
    loss_carryforward: object,
) -> MonthProjection:
    """Project one month. Eligible profit at or below zero pays nothing.

    Inputs are rounded to cents before the split. Half of a positive eligible
    figure is proposed, and the proposal cannot exceed $2,000.00. A loss,
    including one left from an earlier month, becomes the outgoing carryforward.
    A positive carryforward is rejected: retained profit is not a loss.
    """

    realised = _cents(_as_decimal(realised_profit, "realised_profit"))
    paid_costs = _cents(_as_decimal(costs, "costs"))
    carry_in = _cents(_as_decimal(loss_carryforward, "loss_carryforward"))
    if paid_costs < 0:
        raise TreasuryInputError("costs cannot be negative.")
    if carry_in > 0:
        raise TreasuryInputError("loss carryforward cannot be positive.")
    eligible = realised - paid_costs + carry_in
    if eligible <= 0:
        return MonthProjection(
            realised_profit=realised,
            costs=paid_costs,
            loss_carryforward=carry_in,
            eligible_profit=eligible,
            proposed_distribution=Decimal("0.00"),
            retained=Decimal("0.00"),
            loss_carryforward_out=eligible,
        )
    proposed = min(_cents(eligible * DISTRIBUTION_FRACTION), DISTRIBUTION_CAP)
    return MonthProjection(
        realised_profit=realised,
        costs=paid_costs,
        loss_carryforward=carry_in,
        eligible_profit=eligible,
        proposed_distribution=proposed,
        retained=eligible - proposed,
        loss_carryforward_out=Decimal("0.00"),
    )


def review_date(year: int, month: int) -> date:
    """The 5th of the following month. Saturday and Sunday move to Monday."""

    if isinstance(year, bool) or isinstance(month, bool):
        raise TreasuryInputError("year and month must be integers.")
    if not isinstance(year, int) or not isinstance(month, int):
        raise TreasuryInputError("year and month must be integers.")
    if month < 1 or month > 12:
        raise TreasuryInputError("month must be from 1 to 12.")
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1
    day = date(next_year, next_month, REVIEW_DAY)
    if day.weekday() == 5:
        return day + timedelta(days=2)
    if day.weekday() == 6:
        return day + timedelta(days=1)
    return day
