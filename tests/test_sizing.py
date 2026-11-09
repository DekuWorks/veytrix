from decimal import Decimal

import pytest

from veytrix_risk.sizing import (
    DEFAULT_POLICY,
    STOPS_NOT_ENFORCED,
    PolicyError,
    RiskPolicy,
    SizingError,
    SizingResult,
    size_position,
)


def _policy(**overrides: object) -> RiskPolicy:
    values: dict[str, object] = {
        "name": "custom-paper",
        "per_trade_risk_fraction": Decimal("0.005"),
        "daily_loss_stop_fraction": Decimal("0.01"),
        "weekly_loss_stop_fraction": Decimal("0.03"),
        "max_allocation_fraction": Decimal("0.10"),
    }
    values.update(overrides)
    return RiskPolicy(**values)  # type: ignore[arg-type]


def test_allocation_binds_on_the_worked_example() -> None:
    result = size_position("100000.00", "50.00", "48.00")

    assert result.shares == 200
    assert result.binding_constraint == "allocation"
    assert result.stop_distance == Decimal("2.00")
    assert result.risk_budget == Decimal("500.00")
    assert result.planned_risk_amount == Decimal("400.00")
    assert result.notional == Decimal("10000.00")
    assert result.execution_permitted is False
    assert result.order_submitted is False
    assert result.daily_stop_enforced is False
    assert result.weekly_stop_enforced is False
    assert result.note == STOPS_NOT_ENFORCED


def test_risk_binds_when_the_stop_is_wider() -> None:
    result = size_position(Decimal("100000"), Decimal("100"), Decimal("90"))

    assert result.shares == 50
    assert result.binding_constraint == "risk"
    assert result.planned_risk_amount == Decimal("500")


def test_equal_constraints_report_both() -> None:
    result = size_position("100000", "100", "95")

    assert result.shares == 100
    assert result.binding_constraint == "both"


def test_fractional_shares_floor_to_zero() -> None:
    result = size_position("10.00", "50.00", "49.00")

    assert result.shares == 0
    assert result.binding_constraint == "none"
    assert result.warning is not None
    assert result.order_submitted is False


def test_daily_and_weekly_stops_do_not_change_the_share_count() -> None:
    wider_daily = _policy(daily_loss_stop_fraction=Decimal("0.015"))
    tighter_weekly = _policy(weekly_loss_stop_fraction=Decimal("0.02"))
    wider = size_position("100000", "50", "48", policy=wider_daily)
    tighter = size_position("100000", "50", "48", policy=tighter_weekly)

    assert wider.shares == tighter.shares == 200
    assert wider.daily_stop_enforced is False
    assert tighter.weekly_stop_enforced is False


def test_absolute_ceiling_allows_two_percent_and_rejects_anything_above() -> None:
    policy = _policy(per_trade_risk_fraction=Decimal("0.02"))
    allowed = size_position("100000", "50", "48", risk_fraction="0.02", policy=policy)

    assert allowed.risk_fraction == Decimal("0.02")
    with pytest.raises(SizingError, match="absolute ceiling"):
        size_position("100000", "50", "48", risk_fraction="0.0200001", policy=policy)


def test_request_cannot_exceed_the_configured_policy() -> None:
    with pytest.raises(SizingError, match="configured paper policy"):
        size_position("100000", "50", "48", risk_fraction="0.02")
    with pytest.raises(SizingError, match="configured paper policy"):
        size_position("100000", "50", "48", max_allocation_fraction="0.11")


def test_rejects_shorts_floats_and_invalid_stops() -> None:
    with pytest.raises(SizingError, match="Shorting"):
        size_position("100000", "50", "48", side="short")
    with pytest.raises(SizingError, match="Decimal"):
        size_position(100000.0, "50", "48")  # type: ignore[arg-type]
    with pytest.raises(SizingError, match="Decimal"):
        size_position(True, "50", "48")  # type: ignore[arg-type]
    with pytest.raises(SizingError, match="below the entry"):
        size_position("100000", "50", "50")
    with pytest.raises(SizingError, match="below the entry"):
        size_position("100000", "50", "51")
    with pytest.raises(SizingError, match="positive"):
        size_position("0", "50", "48")


def test_policy_cannot_weaken_the_hard_checks() -> None:
    with pytest.raises(PolicyError):
        _policy(risk_fraction_ceiling=Decimal("0.05"))
    with pytest.raises(PolicyError):
        _policy(per_trade_risk_fraction=Decimal("0.03"))
    with pytest.raises(PolicyError):
        _policy(daily_stop_enforced=True)
    with pytest.raises(PolicyError):
        _policy(trading_mode="live")
    with pytest.raises(SizingError):
        SizingResult(
            shares=1,
            binding_constraint="risk",
            stop_distance=Decimal("1"),
            planned_risk_amount=Decimal("1"),
            risk_budget=Decimal("1"),
            notional=Decimal("1"),
            account_equity=Decimal("1"),
            entry_price=Decimal("1"),
            stop_price=Decimal("1"),
            risk_fraction=Decimal("0.005"),
            max_allocation_fraction=Decimal("0.10"),
            daily_loss_stop_fraction=Decimal("0.01"),
            weekly_loss_stop_fraction=Decimal("0.03"),
            policy_name="bad",
            warning=None,
            execution_permitted=True,
        )


def test_default_policy_matches_the_sprint_example() -> None:
    assert DEFAULT_POLICY.per_trade_risk_fraction == Decimal("0.005")
    assert DEFAULT_POLICY.daily_loss_stop_fraction == Decimal("0.01")
    assert DEFAULT_POLICY.weekly_loss_stop_fraction == Decimal("0.03")
    assert DEFAULT_POLICY.max_allocation_fraction == Decimal("0.10")
    assert DEFAULT_POLICY.trading_mode == "paper"
