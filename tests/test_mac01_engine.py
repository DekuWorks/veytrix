from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from mac01_helpers import (
    AFTER_CLOSE,
    LAST_SESSION,
    FakeBroker,
    TimeoutAfterAccepting,
    account,
    broker_order,
    config,
    make_engine,
    market_data,
    orders,
    position,
    signals,
    sqlite_engine,
    state,
)
from veytrix_api.models import Mac01OrderRow
from veytrix_quant.mac01.alpaca_trading import AssetFlags, BrokerRejected, BrokerTimeout
from veytrix_quant.mac01.engine import buy_notional, client_order_id_for
from veytrix_quant.mac01.ledger import Ledger

pytestmark = pytest.mark.filterwarnings("ignore::sqlalchemy.exc.SAWarning")

VERSION = "mac-01.3"
BUY_ID = client_order_id_for("paper", VERSION, "AAPL", LAST_SESSION, "BUY")
SELL_ID = client_order_id_for("paper", VERSION, "AAPL", LAST_SESSION, "SELL")


def test_client_order_id_is_deterministic_per_mode_version_symbol_date_and_side() -> None:
    again = client_order_id_for("paper", VERSION, "AAPL", LAST_SESSION, "BUY")
    variants = {
        client_order_id_for("live", VERSION, "AAPL", LAST_SESSION, "BUY"),
        client_order_id_for("paper", "mac-01.2", "AAPL", LAST_SESSION, "BUY"),
        client_order_id_for("paper", VERSION, "AAPL", date(2026, 11, 5), "BUY"),
        SELL_ID,
    }

    assert again == BUY_ID
    assert BUY_ID not in variants and len(variants) == 4
    assert BUY_ID.startswith("mac01-paper-") and len(BUY_ID) <= 128


def test_buy_signal_submits_one_notional_day_market_order() -> None:
    engine = sqlite_engine()
    broker = FakeBroker()

    result = make_engine(engine, broker).run()

    assert result.status == "ok" and result.decision == "SUBMITTED", result.reason
    [request] = broker.submitted
    assert (request.symbol, request.side) == ("AAPL", "buy")
    assert request.notional == Decimal("100.00") and request.qty is None
    assert (request.type, request.time_in_force) == ("market", "day")
    assert request.client_order_id == BUY_ID
    [row] = orders(engine)
    assert (row.mode, row.status, row.notional, row.qty) == (
        "paper",
        "accepted",
        Decimal("100.00"),
        None,
    )
    assert row.filled_qty == 0 and row.filled_avg_price is None
    [signal] = signals(engine)
    assert signal.side == "BUY" and signal.decision == "SUBMITTED"
    assert state(engine).last_run_status == "ok" and state(engine).last_mode == "paper"


@pytest.mark.parametrize(
    ("per_trade", "position_cap", "held", "expected"),
    [
        ("100.00", "100.00", "0", "100.00"),
        ("25.50", "100.00", "0", "25.50"),
        ("100.00", "100.00", "40.004", "59.99"),
        ("50.00", "100.00", "75.00", "25.00"),
        ("100.00", "100.00", "100.00", "0.00"),
        ("100.00", "100.00", "250.00", "0.00"),
        ("100.00", "100.00", "-5", "100.00"),
    ],
)
def test_notional_cap_maths_is_decimal_and_rounds_down_to_cents(
    per_trade: str, position_cap: str, held: str, expected: str
) -> None:
    cfg = config(max_notional_per_trade=per_trade, max_position_notional=position_cap)

    amount = buy_notional(cfg, Decimal(held))

    assert isinstance(amount, Decimal)
    assert amount == Decimal(expected)
    assert amount.as_tuple().exponent == -2
    assert amount <= Decimal("100.00")


def test_configured_per_trade_cap_is_what_gets_submitted() -> None:
    engine = sqlite_engine()
    broker = FakeBroker()

    make_engine(engine, broker, max_notional_per_trade="37.15").run()

    assert broker.submitted[0].notional == Decimal("37.15")


def test_duplicate_run_for_the_same_session_submits_once() -> None:
    engine = sqlite_engine()
    broker = FakeBroker()

    first = make_engine(engine, broker).run()
    second = make_engine(engine, broker).run()

    assert first.decision == "SUBMITTED"
    assert second.decision == "NO_ACTION"
    assert "already recorded" in second.reason
    assert len(broker.submitted) == 1
    assert len(orders(engine)) == 1
    assert len(signals(engine)) == 1


def test_restart_does_not_trade() -> None:
    engine = sqlite_engine()
    broker = FakeBroker()
    make_engine(engine, broker).run()

    restarted_broker = FakeBroker(orders_by_client_id=dict(broker.orders_by_client_id))
    result = make_engine(engine, restarted_broker).run()

    assert restarted_broker.submitted == []
    assert result.decision == "NO_ACTION"
    assert restarted_broker.lookups == [BUY_ID]


def test_crash_before_submit_is_reconciled_and_not_resubmitted() -> None:
    engine = sqlite_engine()
    make_engine(engine, FakeBroker(), submit_flag=False).run()
    Ledger(engine).insert_pending_order(
        Mac01OrderRow(
            client_order_id=BUY_ID,
            mode="paper",
            strategy_version=VERSION,
            symbol="AAPL",
            session_date=LAST_SESSION,
            side="buy",
            notional=Decimal("100.00"),
            qty=None,
            order_type="market",
            time_in_force="day",
            status="pending_submit",
            filled_qty=Decimal(0),
        )
    )
    broker = FakeBroker()

    result = make_engine(engine, broker).run()

    assert broker.submitted == []
    assert result.decision == "NO_ACTION"
    assert orders(engine)[0].status == "not_found"


def test_timeout_looks_up_by_client_order_id_and_does_not_retry() -> None:
    engine = sqlite_engine()
    broker = TimeoutAfterAccepting()

    result = make_engine(engine, broker).run()

    assert len(broker.submitted) == 1
    assert broker.lookups == [BUY_ID]
    assert result.decision == "SUBMITTED"
    assert orders(engine)[0].status == "accepted"


def test_timeout_without_a_broker_record_stays_unconfirmed_then_not_found() -> None:
    engine = sqlite_engine()
    broker = FakeBroker(submit_error=BrokerTimeout("timed out"))

    first = make_engine(engine, broker).run()

    assert first.decision == "UNCONFIRMED" and first.status == "error"
    assert len(broker.submitted) == 1
    assert orders(engine)[0].status == "unconfirmed"

    broker.submit_error = None
    second = make_engine(engine, broker).run()

    assert len(broker.submitted) == 1, "a timeout must never be blindly retried"
    assert second.decision == "NO_ACTION"
    assert orders(engine)[0].status == "not_found"


def test_rejected_order_is_recorded() -> None:
    engine = sqlite_engine()
    broker = FakeBroker(submit_error=BrokerRejected(403, "insufficient buying power"))

    result = make_engine(engine, broker).run()

    assert result.decision == "REJECTED" and result.status == "blocked"
    [row] = orders(engine)
    assert row.status == "rejected"
    assert row.last_error is not None and "insufficient buying power" in row.last_error
    assert signals(engine)[0].decision == "REJECTED"


def test_partial_fill_is_tracked_and_fill_is_only_what_the_broker_reports() -> None:
    engine = sqlite_engine()
    broker = FakeBroker()
    make_engine(engine, broker).run()
    assert orders(engine)[0].filled_avg_price is None

    broker.orders_by_client_id[BUY_ID] = broker_order(
        BUY_ID, status="partially_filled", filled_qty="0.4", filled_avg_price="110.25"
    )
    make_engine(engine, broker).run()
    row = orders(engine)[0]
    assert row.status == "partially_filled"
    assert row.filled_qty == Decimal("0.4")
    assert row.filled_avg_price == Decimal("110.25")

    broker.orders_by_client_id[BUY_ID] = broker_order(
        BUY_ID, status="filled", filled_qty="0.906618314", filled_avg_price="110.30"
    )
    make_engine(engine, broker).run()
    row = orders(engine)[0]
    assert row.status == "filled" and row.filled_qty == Decimal("0.906618314")
    assert len(broker.submitted) == 1


def test_sell_with_no_position_is_no_action() -> None:
    engine = sqlite_engine()
    broker = FakeBroker(position=None)

    result = make_engine(engine, broker, kind="SELL").run()

    assert result.side == "SELL"
    assert result.decision == "NO_ACTION" and "no position" in result.reason
    assert broker.submitted == []
    assert orders(engine) == []


def test_sell_while_holding_closes_the_whole_fractional_position() -> None:
    engine = sqlite_engine()
    broker = FakeBroker(position=position("0.906618314"))

    result = make_engine(engine, broker, kind="SELL").run()

    assert result.decision == "SUBMITTED", result.reason
    [request] = broker.submitted
    assert (request.side, request.qty, request.notional) == (
        "sell",
        Decimal("0.906618314"),
        None,
    )
    assert request.client_order_id == SELL_ID
    assert orders(engine)[0].qty == Decimal("0.906618314")


def test_sell_is_blocked_when_part_of_the_position_is_held_by_another_order() -> None:
    engine = sqlite_engine()
    broker = FakeBroker(position=position("0.9", available="0.4"))

    result = make_engine(engine, broker, kind="SELL").run()

    assert result.decision == "BLOCKED" and "held by another order" in result.reason
    assert broker.submitted == []


def test_short_position_is_never_added_to() -> None:
    engine = sqlite_engine()
    broker = FakeBroker(position=position("-1", side="short"))

    for kind in ("BUY", "SELL"):
        result = make_engine(engine, broker, kind=kind).run()
        assert result.decision == "BLOCKED" and "long only" in result.reason
    assert broker.submitted == []


def test_buy_while_already_long_is_no_action() -> None:
    engine = sqlite_engine()
    broker = FakeBroker(position=position("0.5"))

    result = make_engine(engine, broker).run()

    assert result.decision == "NO_ACTION" and "already long" in result.reason
    assert broker.submitted == []


def test_hold_never_submits() -> None:
    engine = sqlite_engine()
    broker = FakeBroker()

    result = make_engine(engine, broker, kind="HOLD").run()

    assert result.decision == "NO_ACTION" and broker.submitted == []


@pytest.mark.parametrize("where", ["config", "state"])
def test_kill_switch_blocks(where: str) -> None:
    engine = sqlite_engine()
    broker = FakeBroker()
    if where == "state":
        Ledger(engine).set_flags(kill_switch=True)
        runner = make_engine(engine, broker)
    else:
        runner = make_engine(engine, broker, kill_switch=True)

    result = runner.run()

    assert result.decision == "BLOCKED" and "kill switch" in result.reason
    assert broker.submitted == []


def test_pause_blocks_and_resume_allows() -> None:
    engine = sqlite_engine()
    broker = FakeBroker()
    Ledger(engine).set_flags(paused=True)

    paused = make_engine(engine, broker).run()
    assert paused.decision == "BLOCKED" and "paused" in paused.reason
    assert broker.submitted == []

    Ledger(engine).set_flags(paused=False)
    resumed = make_engine(engine, broker).run()
    assert resumed.decision == "SUBMITTED"


@pytest.mark.parametrize(
    ("config_submit", "flag"),
    [(False, True), (True, False), (False, False)],
)
def test_paper_dry_run_never_calls_submit(config_submit: bool, flag: bool) -> None:
    engine = sqlite_engine()
    broker = FakeBroker()

    result = make_engine(engine, broker, submit_flag=flag, submit_orders=config_submit).run()

    assert result.decision == "DRY_RUN" and result.status == "ok"
    assert "would submit buy $100.00 notional AAPL" in result.reason
    assert broker.submitted == []
    assert orders(engine) == []


def test_dry_run_then_submit_for_the_same_session_submits_once() -> None:
    engine = sqlite_engine()
    broker = FakeBroker()

    make_engine(engine, broker, submit_flag=False).run()
    make_engine(engine, broker).run()
    make_engine(engine, broker).run()

    assert len(broker.submitted) == 1


def test_stale_data_blocks_entry_and_records_no_signal() -> None:
    engine = sqlite_engine()
    broker = FakeBroker()
    stale = market_data("BUY", through=date(2026, 11, 5))

    result = make_engine(engine, broker, data=stale).run()

    assert result.decision == "DATA_BLOCKED" and "stale" in result.reason
    assert broker.submitted == [] and broker.lookups == []
    assert signals(engine) == []
    assert state(engine).last_run_status == "blocked"


@pytest.mark.parametrize(
    ("snapshot", "reason"),
    [
        (account(status="ACCOUNT_UPDATED"), "account status"),
        (account(trading_blocked=True), "blocked"),
        (account(account_blocked=True), "blocked"),
        (account(cash=Decimal("99.99")), "insufficient"),
        (account(buying_power=Decimal("50")), "insufficient"),
        (account(equity=Decimal(480)), "daily loss"),
        (account(last_equity=None), "daily loss"),
    ],
)
def test_account_checks_block(snapshot, reason: str) -> None:
    engine = sqlite_engine()
    broker = FakeBroker(account_snapshot=snapshot)

    result = make_engine(engine, broker).run()

    assert result.decision == "BLOCKED", result.reason
    assert reason in result.reason
    assert broker.submitted == []


@pytest.mark.parametrize(
    ("flags", "reason"),
    [(AssetFlags(False, True), "not tradable"), (AssetFlags(True, False), "not fractionable")],
)
def test_asset_must_be_tradable_and_fractionable_for_a_notional_buy(flags, reason) -> None:
    engine = sqlite_engine()
    broker = FakeBroker(asset=flags)

    result = make_engine(engine, broker).run()

    assert result.decision == "BLOCKED" and reason in result.reason
    assert broker.submitted == []


@pytest.mark.parametrize("side", ["buy", "sell"])
def test_any_open_order_blocks_one_order_at_a_time(side: str) -> None:
    engine = sqlite_engine()
    broker = FakeBroker(open_orders=[broker_order("manual-order", side=side)])

    result = make_engine(engine, broker).run()

    assert result.decision == "BLOCKED" and "one at a time" in result.reason
    assert broker.submitted == []


def _earlier_orders(engine, modes: tuple[str, ...]) -> None:
    ledger = Ledger(engine)
    for index, mode in enumerate(modes):
        ledger.insert_pending_order(
            Mac01OrderRow(
                client_order_id=f"earlier-{index}",
                mode=mode,
                strategy_version=VERSION,
                symbol="AAPL",
                session_date=date(2026, 11, 5),
                side="buy",
                notional=Decimal("10.00"),
                order_type="market",
                time_in_force="day",
                status="filled",
                filled_qty=Decimal("0.1"),
                created_at=datetime(2026, 11, 9, 14, 0, tzinfo=UTC),
            )
        )


def test_max_orders_per_day_blocks_at_the_cap() -> None:
    engine = sqlite_engine()
    _earlier_orders(engine, ("paper", "paper"))
    broker = FakeBroker()

    result = make_engine(engine, broker).run()

    assert result.decision == "BLOCKED" and "max orders per day" in result.reason
    assert broker.submitted == []


def test_max_orders_per_day_counts_this_mode_only() -> None:
    engine = sqlite_engine()
    _earlier_orders(engine, ("paper", "live", "live"))
    broker = FakeBroker()

    result = make_engine(engine, broker).run()

    assert result.decision == "SUBMITTED", result.reason


def test_submission_outside_regular_hours_is_blocked_but_dry_run_reports_it() -> None:
    engine = sqlite_engine()
    broker = FakeBroker()

    blocked = make_engine(engine, broker, now=AFTER_CLOSE).run()

    assert blocked.decision == "BLOCKED" and "outside regular hours" in blocked.reason
    assert broker.submitted == []

    dry = make_engine(sqlite_engine(), broker, now=AFTER_CLOSE, submit_flag=False).run()
    assert dry.decision == "DRY_RUN" and "timing: outside regular hours" in dry.reason


def test_submission_near_the_close_is_blocked() -> None:
    engine = sqlite_engine()
    broker = FakeBroker()
    near_close = datetime(2026, 11, 9, 20, 50, tzinfo=UTC)  # 15:50 New York

    result = make_engine(engine, broker, now=near_close).run()

    assert result.decision == "BLOCKED" and "outside regular hours" in result.reason
    assert broker.submitted == []


def test_reconcile_failure_blocks_new_orders() -> None:
    engine = sqlite_engine()
    broker = FakeBroker(submit_error=BrokerTimeout("timed out"))
    make_engine(engine, broker).run()

    broker.lookup_error = BrokerTimeout("network down")
    broker.submit_error = None
    result = make_engine(engine, broker).run()

    assert result.status == "error" and "reconcile failed" in result.reason
    assert len(broker.submitted) == 1


def test_secret_values_are_masked_in_recorded_reasons() -> None:
    engine = sqlite_engine()
    planted = "PLANTED-VALUE-123"
    broker = FakeBroker(submit_error=BrokerRejected(401, f"bad credentials {planted}"))

    result = make_engine(engine, broker, secrets=(planted,)).run()

    assert planted not in result.reason
    assert planted not in (orders(engine)[0].last_error or "")
    assert planted not in (state(engine).last_run_message or "")
