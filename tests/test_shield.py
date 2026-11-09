"""The local shield preview cannot release an order."""

from decimal import Decimal

import pytest

from veytrix_risk.shield import ShieldInputError, preview_order


def _preview(**overrides: object):
    payload = {
        "symbol": "AAPL",
        "side": "long",
        "limit_price": "50.00",
        "quantity": "2",
        "position_notional": "0.00",
        "orders_today": 0,
        "quote_age_seconds": 30,
        "leverage": "1",
    }
    payload.update(overrides)
    return preview_order(**payload)


def test_a_hundred_dollar_buy_passes_and_still_cannot_execute() -> None:
    first = _preview()
    second = _preview()

    assert first == second
    assert first.rule_result == "pass"
    assert first.reasons == ()
    assert first.notional == Decimal("100.00")
    assert first.position_after == Decimal("100.00")
    assert first.release == "withheld"
    assert first.buying_power_checked is False
    assert first.owner_approved is False
    assert first.execution_permitted is False
    assert first.order_submitted is False


def test_local_rules_fail_together_without_releasing() -> None:
    decision = _preview(
        symbol="MSFT",
        side="short",
        limit_price="100.01",
        quantity="1",
        position_notional="50.00",
        orders_today=2,
        quote_age_seconds=121,
        leverage="2",
    )

    assert decision.rule_result == "fail"
    assert decision.reasons == (
        "short",
        "leverage",
        "symbol",
        "stale",
        "notional",
        "position",
        "daily_orders",
    )
    assert decision.execution_permitted is False
    assert decision.release == "withheld"


def test_a_quote_at_120_seconds_stays_fresh_and_121_is_stale() -> None:
    assert _preview(quote_age_seconds=120).rule_result == "pass"
    stale = _preview(quote_age_seconds=121)
    assert stale.reasons == ("stale",)


def test_one_cent_over_the_position_cap_fails() -> None:
    decision = _preview(limit_price="50.00", quantity="1", position_notional="50.01")
    assert decision.reasons == ("position",)
    assert decision.position_after == Decimal("100.01")


def test_floats_and_a_non_positive_price_are_rejected() -> None:
    with pytest.raises(ShieldInputError):
        _preview(limit_price=50.0)
    with pytest.raises(ShieldInputError):
        _preview(limit_price="0")
    with pytest.raises(ShieldInputError):
        _preview(position_notional="-1")
