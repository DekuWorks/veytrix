"""The local reservation preview cannot write a row or release an order."""

from decimal import Decimal

import pytest

from veytrix_api.schemas import AGENT_CODES
from veytrix_risk.reservation import DESKS, ReservationInputError, preview_reservation


def _held(agent: str = "DAY-01", notional: str = "60.00", key: str = "day-60") -> dict[str, str]:
    return {"agent": agent, "notional": notional, "idempotency_key": key}


def _preview(**overrides: object):
    payload = {
        "agent": "STOCK-01",
        "notional": "40.00",
        "idempotency_key": "stock-40",
        "outstanding": (),
    }
    payload.update(overrides)
    return preview_reservation(**payload)


def test_reservation_desks_match_the_registry() -> None:
    assert DESKS == AGENT_CODES


def test_forty_dollars_passes_and_still_reserves_nothing() -> None:
    first = _preview()
    second = _preview()

    assert first == second
    assert first.rule_result == "pass"
    assert first.reasons == ()
    assert first.requested == Decimal("40.00")
    assert first.reserved_before == Decimal("0.00")
    assert first.reserved_after == Decimal("40.00")
    assert first.release == "withheld"
    assert first.persisted is False
    assert first.lock == "absent"
    assert first.buying_power_checked is False
    assert first.broker_reconciled is False
    assert first.execution_permitted is False
    assert first.order_submitted is False


def test_the_same_key_is_not_added_twice() -> None:
    first = _preview(agent="DAY-01", notional="60.00", idempotency_key="day-60")
    second = _preview(
        agent="DAY-01",
        notional="60.00",
        idempotency_key="day-60",
        outstanding=(_held(),),
    )

    assert first.reserved_after == Decimal("60.00")
    assert second.rule_result == "pass"
    assert second.reasons == ()
    assert second.reserved_before == Decimal("60.00")
    assert second.reserved_after == Decimal("60.00")
    assert second.persisted is False


def test_a_second_desk_stops_at_one_hundred() -> None:
    under = _preview(outstanding=(_held(),))
    over = _preview(notional="40.01", outstanding=(_held(),))
    exact = _preview(notional="40.00", outstanding=(_held(),))

    assert under.rule_result == "pass"
    assert under.reserved_after == Decimal("100.00")
    assert exact.reserved_after == Decimal("100.00")
    assert over.rule_result == "fail"
    assert over.reasons == ("book",)
    assert over.reserved_before == Decimal("60.00")
    assert over.reserved_after == Decimal("60.00")
    assert over.execution_permitted is False


def test_two_unseen_previews_both_pass_because_there_is_no_lock() -> None:
    day = _preview(agent="DAY-01", notional="60.00", idempotency_key="day-60")
    stock = _preview()

    assert day.rule_result == "pass"
    assert stock.rule_result == "pass"
    assert day.lock == "absent"
    assert stock.lock == "absent"
    assert day.reserved_after == Decimal("60.00")
    assert stock.reserved_after == Decimal("40.00")


def test_unknown_desk_reused_key_and_over_book_fail_together() -> None:
    decision = _preview(
        agent="NOBODY",
        notional="50.00",
        idempotency_key="day-60",
        outstanding=(_held(),),
    )

    assert decision.rule_result == "fail"
    assert decision.reasons == ("agent", "idempotency", "book")
    assert decision.reserved_after == decision.reserved_before
    assert decision.release == "withheld"
    assert decision.order_submitted is False


def test_a_second_key_for_the_same_desk_fails() -> None:
    decision = _preview(
        agent="DAY-01",
        notional="10.00",
        idempotency_key="day-10",
        outstanding=(_held(),),
    )

    assert decision.reasons == ("agent",)
    assert decision.reserved_after == Decimal("60.00")


def test_floats_and_a_non_positive_notional_are_rejected() -> None:
    with pytest.raises(ReservationInputError):
        _preview(notional=40.0)
    with pytest.raises(ReservationInputError):
        _preview(notional="0.00")
    with pytest.raises(ReservationInputError):
        _preview(idempotency_key="Day-60")
