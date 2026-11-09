"""Market data and exchange calendar interfaces, plus validation of completed daily closes."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Protocol
from zoneinfo import ZoneInfo

NEW_YORK = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class DailyBar:
    session_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


@dataclass(frozen=True)
class TradingSession:
    session_date: date
    open: datetime
    close: datetime


class MarketDataProvider(Protocol):
    source: str

    def daily_bars(self, symbol: str, start: date, end: date) -> list[DailyBar]:
        """Split- and dividend-adjusted daily bars, inclusive of start and end."""


class TradingCalendar(Protocol):
    def sessions(self, start: date, end: date) -> list[TradingSession]:
        """Regular trading sessions, inclusive, with America/New_York open and close."""


class DataUnavailable(RuntimeError):
    """The provider could not return bars or calendar sessions."""


def session_from_strings(day: str, open_hhmm: str, close_hhmm: str) -> TradingSession:
    session_date = date.fromisoformat(day)
    open_time = time.fromisoformat(open_hhmm)
    close_time = time.fromisoformat(close_hhmm)
    return TradingSession(
        session_date=session_date,
        open=datetime.combine(session_date, open_time, tzinfo=NEW_YORK),
        close=datetime.combine(session_date, close_time, tzinfo=NEW_YORK),
    )


@dataclass(frozen=True)
class CloseSeries:
    dates: tuple[date, ...]
    closes: tuple[Decimal, ...]
    dropped_incomplete: int


@dataclass(frozen=True)
class DataCheck:
    ok: bool
    reason: str
    series: CloseSeries | None
    latest_completed: TradingSession | None
    next_session: TradingSession | None


def completed_and_next(
    sessions: Sequence[TradingSession], now: datetime
) -> tuple[list[TradingSession], TradingSession | None]:
    ordered = sorted(sessions, key=lambda item: item.session_date)
    completed = [item for item in ordered if item.close <= now]
    later = [item for item in ordered if item.close > now]
    return completed, (later[0] if later else None)


def validate_closes(
    bars: Sequence[DailyBar],
    sessions: Sequence[TradingSession],
    now: datetime,
    history_trading_days: int,
    minimum_closes: int,
) -> DataCheck:
    """Drop the incomplete session, then require exactly the expected completed sessions.

    The last bar must be the most recent closed session on the calendar. Duplicates, bars
    on non-session dates, gaps, and missing or non-Decimal closes all fail.
    """

    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware.")
    completed, upcoming = completed_and_next(sessions, now)
    if not completed:
        return DataCheck(False, "calendar has no completed session", None, None, upcoming)
    latest = completed[-1]
    if upcoming is None:
        return DataCheck(False, "calendar has no next session", None, latest, None)
    session_dates = {item.session_date for item in sessions}
    expected = [item.session_date for item in completed[-history_trading_days:]]

    rows: dict[date, Decimal] = {}
    dropped = 0
    for bar in bars:
        if bar.session_date > latest.session_date:
            dropped += 1
            continue
        if bar.session_date < expected[0]:
            continue
        if bar.session_date not in session_dates:
            return DataCheck(
                False, f"bar on non-session date {bar.session_date}", None, latest, upcoming
            )
        if bar.session_date in rows:
            return DataCheck(False, f"duplicate bar for {bar.session_date}", None, latest, upcoming)
        close = bar.close
        if not isinstance(close, Decimal) or not close.is_finite() or close <= 0:
            return DataCheck(
                False, f"missing or invalid close on {bar.session_date}", None, latest, upcoming
            )
        rows[bar.session_date] = close

    if not rows:
        return DataCheck(False, "no completed bars", None, latest, upcoming)
    last_date = max(rows)
    if last_date != latest.session_date:
        return DataCheck(
            False,
            f"stale data: last bar {last_date}, last closed session {latest.session_date}",
            None,
            latest,
            upcoming,
        )
    missing = [day for day in expected if day not in rows]
    if missing:
        shown = ", ".join(str(day) for day in missing[:5])
        return DataCheck(False, f"missing sessions: {shown}", None, latest, upcoming)
    if len(expected) < minimum_closes:
        return DataCheck(
            False,
            f"insufficient history: {len(expected)} of {minimum_closes} closes",
            None,
            latest,
            upcoming,
        )
    series = CloseSeries(
        dates=tuple(expected),
        closes=tuple(rows[day] for day in expected),
        dropped_incomplete=dropped,
    )
    return DataCheck(True, "ok", series, latest, upcoming)


class FixtureCalendar:
    """Weekday sessions, 09:30 to 16:00 New York, minus the supplied holidays."""

    def __init__(
        self,
        holidays: Sequence[date] = (),
        early_closes: dict[date, str] | None = None,
    ) -> None:
        self.holidays = frozenset(holidays)
        self.early_closes = dict(early_closes or {})

    def sessions(self, start: date, end: date) -> list[TradingSession]:
        out: list[TradingSession] = []
        day = start
        while day <= end:
            if day.weekday() < 5 and day not in self.holidays:
                close = self.early_closes.get(day, "16:00")
                out.append(session_from_strings(day.isoformat(), "09:30", close))
            day += timedelta(days=1)
        return out


class FixtureMarketData:
    """Returns the bars it was given. Synthetic; not a market price."""

    source = "fixture"

    def __init__(self, bars: Sequence[DailyBar]) -> None:
        self.bars = list(bars)
        self.calls: list[tuple[str, date, date]] = []

    def daily_bars(self, symbol: str, start: date, end: date) -> list[DailyBar]:
        self.calls.append((symbol, start, end))
        return [bar for bar in self.bars if start <= bar.session_date <= end]


def bars_from_closes(
    sessions: Sequence[TradingSession], closes: Sequence[Decimal]
) -> list[DailyBar]:
    """Flat OHLC bars for tests. The open equals the previous close."""

    if len(sessions) != len(closes):
        raise ValueError("sessions and closes differ in length.")
    out: list[DailyBar] = []
    previous = closes[0] if closes else Decimal(0)
    for session, close in zip(sessions, closes, strict=True):
        high = max(previous, close)
        low = min(previous, close)
        out.append(DailyBar(session.session_date, previous, high, low, close, Decimal(1000)))
        previous = close
    return out


def synthetic_closes(count: int, seed: int = 7, start: Decimal = Decimal("200")) -> list[Decimal]:
    """Deterministic synthetic walk with slow regime changes. Not AAPL. Not a market price."""

    state = seed & 0x7FFFFFFF or 1
    price = start
    out: list[Decimal] = []
    for index in range(count):
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        noise = Decimal((state % 2001) - 1000) / Decimal(100000)
        drift = Decimal("0.004") if (index // 60) % 2 == 0 else Decimal("-0.004")
        price = (price * (Decimal(1) + drift + noise)).quantize(Decimal("0.01"))
        out.append(price)
    return out
