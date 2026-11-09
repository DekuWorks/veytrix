import statistics
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from mac01_helpers import HOLIDAYS, LAST_SESSION, RUN_AT, calendar, completed_sessions
from veytrix_quant.mac01.backtest import HYPOTHETICAL_LABEL, CostModel, run_backtest
from veytrix_quant.mac01.data import (
    DailyBar,
    bars_from_closes,
    synthetic_closes,
    validate_closes,
)
from veytrix_quant.mac01.schedule import next_run_at
from veytrix_quant.mac01.strategy import (
    InsufficientHistory,
    crossover_markers,
    evaluate_crossover,
    rolling_sma,
    sma,
)


def _series(values: list[str]) -> list[Decimal]:
    return [Decimal(value) for value in values]


def test_sma_matches_an_independent_decimal_mean() -> None:
    closes = synthetic_closes(80, seed=11)

    for period in (20, 50):
        expected = statistics.mean(closes[-period:])
        assert isinstance(expected, Decimal)
        assert sma(closes, period) == expected
    rolled = rolling_sma(closes, 20)
    assert rolled[18] is None
    assert rolled[-1] == statistics.mean(closes[-20:])


def test_sma_rejects_floats() -> None:
    with pytest.raises(TypeError):
        sma([1.0] * 20, 20)  # type: ignore[list-item]


def test_bullish_crossover_is_buy() -> None:
    closes = [Decimal(200 - index) for index in range(60)]
    closes += [Decimal(141 + 3 * index) for index in range(1, 40)]
    for end in range(51, len(closes) + 1):
        signal = evaluate_crossover(closes[:end])
        if signal.side == "BUY":
            assert signal.fast_prev <= signal.slow_prev
            assert signal.fast_cur > signal.slow_cur
            return
    pytest.fail("expected a bullish crossover")


def test_bearish_crossover_is_sell() -> None:
    closes = [Decimal(100 + index) for index in range(60)]
    closes += [Decimal(159 - 3 * index) for index in range(1, 40)]
    sides = [evaluate_crossover(closes[:end]).side for end in range(51, len(closes) + 1)]
    assert "SELL" in sides
    assert "BUY" not in sides


def test_equality_then_cross_follows_the_inclusive_rule() -> None:
    flat = [Decimal(100)] * 50
    up = evaluate_crossover([*flat, Decimal(101)])
    down = evaluate_crossover([*flat, Decimal(99)])
    still = evaluate_crossover([*flat, Decimal(100)])

    assert (up.fast_prev, up.slow_prev) == (Decimal(100), Decimal(100))
    assert up.side == "BUY"
    assert down.side == "SELL"
    assert still.side == "HOLD"


def test_no_cross_is_hold() -> None:
    rising = [Decimal(100 + index) for index in range(80)]

    assert evaluate_crossover(rising).side == "HOLD"


def test_insufficient_history_needs_51_closes() -> None:
    with pytest.raises(InsufficientHistory):
        evaluate_crossover([Decimal(100)] * 50)
    assert evaluate_crossover([Decimal(100)] * 51).side == "HOLD"


def test_markers_use_the_same_rule() -> None:
    closes = [Decimal(100)] * 50 + [Decimal(110)] + [Decimal(110)] * 5
    dates = [f"d{index}" for index in range(len(closes))]

    assert crossover_markers(dates, closes, 20, 50) == [("d50", "BUY")]


def test_holidays_are_not_gaps_but_missing_sessions_are() -> None:
    sessions = completed_sessions(100)
    session_dates = {item.session_date for item in sessions}
    assert date(2026, 9, 7) not in session_dates
    assert HOLIDAYS
    bars = bars_from_closes(sessions, [Decimal(100)] * 100)
    full = calendar().sessions(date(2026, 1, 1), date(2026, 11, 30))

    ok = validate_closes(bars, full, RUN_AT, 100, 51)
    assert ok.ok, ok.reason
    assert ok.series is not None and ok.series.dates[-1] == LAST_SESSION

    missing = [bar for bar in bars if bar.session_date != date(2026, 10, 14)]
    check = validate_closes(missing, full, RUN_AT, 100, 51)
    assert not check.ok
    assert "missing sessions" in check.reason and "2026-10-14" in check.reason


def test_bar_on_a_holiday_is_rejected() -> None:
    sessions = completed_sessions(100)
    bars = bars_from_closes(sessions, [Decimal(100)] * 100)
    bars.append(DailyBar(date(2026, 9, 7), *(Decimal(100),) * 4, Decimal(1)))
    full = calendar().sessions(date(2026, 1, 1), date(2026, 11, 30))

    check = validate_closes(bars, full, RUN_AT, 100, 51)
    assert not check.ok and "non-session" in check.reason


def test_incomplete_current_session_is_dropped() -> None:
    during = datetime(2026, 11, 6, 20, 0, tzinfo=UTC)  # 15:00 New York, still open
    sessions = completed_sessions(101)
    bars = bars_from_closes(sessions, [Decimal(100)] * 101)
    full = calendar().sessions(date(2026, 1, 1), date(2026, 11, 30))

    check = validate_closes(bars, full, during, 100, 51)
    assert check.ok, check.reason
    assert check.series is not None
    assert check.series.dates[-1] == date(2026, 11, 5)
    assert check.series.dropped_incomplete == 1


def test_stale_duplicate_and_bad_closes_fail() -> None:
    full = calendar().sessions(date(2026, 1, 1), date(2026, 11, 30))
    stale_sessions = completed_sessions(100, through=date(2026, 11, 5))
    stale = bars_from_closes(stale_sessions, [Decimal(100)] * 100)
    check = validate_closes(stale, full, RUN_AT, 100, 51)
    assert not check.ok and "stale" in check.reason

    sessions = completed_sessions(100)
    bars = bars_from_closes(sessions, [Decimal(100)] * 100)
    duplicate = validate_closes([*bars, bars[-1]], full, RUN_AT, 100, 51)
    assert not duplicate.ok and "duplicate" in duplicate.reason

    last = bars[-1]
    bad = DailyBar(last.session_date, last.open, last.high, last.low, 100.0, last.volume)  # type: ignore[arg-type]
    broken = validate_closes([*bars[:-1], bad], full, RUN_AT, 100, 51)
    assert not broken.ok and "invalid close" in broken.reason


def test_schedule_runs_at_0935_new_york_on_trading_days_only() -> None:
    from veytrix_quant.mac01.data import FixtureCalendar

    cal = FixtureCalendar(holidays=[date(2026, 11, 26)], early_closes={date(2026, 11, 27): "13:00"})
    sessions = cal.sessions(date(2026, 11, 25), date(2026, 12, 4))

    before_open = next_run_at(sessions, datetime(2026, 11, 25, 13, 0, tzinfo=UTC))
    assert before_open is not None and before_open.isoformat() == "2026-11-25T09:35:00-05:00"
    after_wed = next_run_at(sessions, datetime(2026, 11, 25, 15, 0, tzinfo=UTC))
    assert after_wed is not None and after_wed.isoformat() == "2026-11-27T09:35:00-05:00"
    friday = next_run_at(sessions, datetime(2026, 11, 27, 15, 0, tzinfo=UTC))
    assert friday is not None and friday.isoformat() == "2026-11-30T09:35:00-05:00"


def test_backtest_fills_at_the_next_open_with_costs_and_is_hypothetical() -> None:
    sessions = calendar().sessions(date(2025, 1, 1), date(2026, 11, 6))[:300]
    bars = bars_from_closes(sessions, synthetic_closes(300, seed=7))

    free = run_backtest(bars)
    costly = run_backtest(
        bars,
        costs=CostModel(Decimal(1), Decimal(10), Decimal(5)),
    )

    assert free.label == HYPOTHETICAL_LABEL and "HYPOTHETICAL" in free.label
    assert free.trades, "fixture should cross at least once"
    by_date = {bar.session_date.isoformat(): bar for bar in bars}
    first = free.trades[0]
    assert first.fill_date > first.signal_date
    assert first.price == by_date[first.fill_date].open
    assert first.side == "buy" and first.qty * first.price <= Decimal("100.00")
    assert Decimal("100.00") - first.qty * first.price < first.price * Decimal("0.000000001")
    assert costly.trades[0].price > first.price
    assert costly.strategy_pnl < free.strategy_pnl
    assert free.buy_and_hold_pnl != Decimal(0)
