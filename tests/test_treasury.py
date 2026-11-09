"""The monthly projection is arithmetic. It does not pay anyone."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from veytrix_risk.treasury import (
    DISTRIBUTION_CAP,
    TreasuryInputError,
    project_month,
    review_date,
)


def test_half_of_a_positive_month_is_proposed_and_capped() -> None:
    ordinary = project_month(realised_profit="100.00", costs="30.00", loss_carryforward="0")
    assert ordinary.eligible_profit == Decimal("70.00")
    assert ordinary.proposed_distribution == Decimal("35.00")
    assert ordinary.retained == Decimal("35.00")
    assert ordinary.loss_carryforward_out == Decimal("0.00")

    capped = project_month(realised_profit="10000.00", costs="0", loss_carryforward="0")
    assert capped.proposed_distribution == DISTRIBUTION_CAP
    assert capped.retained == Decimal("8000.00")
    assert capped.loss_carryforward_out == Decimal("0.00")


def test_a_second_call_does_not_add_another_payout() -> None:
    first = project_month(realised_profit="100.00", costs="0", loss_carryforward="0")
    second = project_month(realised_profit="100.00", costs="0", loss_carryforward="0")
    assert first == second
    assert first.proposed_distribution == Decimal("50.00")


def test_negative_months_carry_forward_and_a_later_month_can_clear_them() -> None:
    loss = project_month(realised_profit="10.00", costs="40.00", loss_carryforward="0")
    assert loss.eligible_profit == Decimal("-30.00")
    assert loss.proposed_distribution == Decimal("0.00")
    assert loss.retained == Decimal("0.00")
    assert loss.loss_carryforward_out == Decimal("-30.00")

    still_short = project_month(
        realised_profit="20.00",
        costs="0",
        loss_carryforward=loss.loss_carryforward_out,
    )
    assert still_short.eligible_profit == Decimal("-10.00")
    assert still_short.proposed_distribution == Decimal("0.00")
    assert still_short.loss_carryforward_out == Decimal("-10.00")

    recovered = project_month(
        realised_profit="40.00",
        costs="0",
        loss_carryforward=still_short.loss_carryforward_out,
    )
    assert recovered.eligible_profit == Decimal("30.00")
    assert recovered.proposed_distribution == Decimal("15.00")
    assert recovered.retained == Decimal("15.00")
    assert recovered.loss_carryforward_out == Decimal("0.00")


def test_zero_and_a_half_cent_do_not_propose_a_payment() -> None:
    zero = project_month(realised_profit="0.00", costs="0.00", loss_carryforward="0.00")
    assert zero.proposed_distribution == Decimal("0.00")
    assert zero.loss_carryforward_out == Decimal("0.00")

    tiny = project_month(realised_profit="0.01", costs="0", loss_carryforward="0")
    assert tiny.eligible_profit == Decimal("0.01")
    assert tiny.proposed_distribution == Decimal("0.00")
    assert tiny.retained == Decimal("0.01")


def test_review_date_keeps_a_weekday_and_moves_a_weekend() -> None:
    weekday = review_date(2026, 10)
    assert weekday == date(2026, 11, 5)
    assert weekday.weekday() < 5

    assert date(2026, 12, 5).weekday() == 5
    assert review_date(2026, 11) == date(2026, 12, 7)

    sunday = None
    for year in range(2026, 2036):
        for month in range(1, 13):
            if month == 12:
                following = date(year + 1, 1, 5)
                source = (year, 12)
            else:
                following = date(year, month + 1, 5)
                source = (year, month)
            if following.weekday() == 6:
                sunday = (source, following)
                break
        if sunday is not None:
            break
    assert sunday is not None
    source, following = sunday
    assert review_date(*source) == following + timedelta(days=1)


def test_floats_positive_carryforward_and_negative_costs_are_rejected() -> None:
    with pytest.raises(TreasuryInputError):
        project_month(realised_profit=100.0, costs="0", loss_carryforward="0")
    with pytest.raises(TreasuryInputError):
        project_month(realised_profit="10", costs="0", loss_carryforward="1.00")
    with pytest.raises(TreasuryInputError):
        project_month(realised_profit="10", costs="-1", loss_carryforward="0")
