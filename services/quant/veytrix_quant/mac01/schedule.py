"""Pick the next run time: 09:35 New York on each trading day, from the Alpaca calendar.

At that time the previous session is complete, so its daily bar is final, and a notional market
DAY order is inside regular hours (Alpaca only fills fractional market orders then).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime, timedelta

from veytrix_quant.mac01.data import TradingSession

RUN_DELAY_AFTER_OPEN = timedelta(minutes=5)
MAX_SLEEP_CHUNK_SECONDS = 300.0


def next_run_at(sessions: Sequence[TradingSession], now: datetime) -> datetime | None:
    """Five minutes after the official open of the next session. None if the window is empty."""

    for session in sorted(sessions, key=lambda item: item.session_date):
        target = session.open + RUN_DELAY_AFTER_OPEN
        if target > now:
            return target
    return None


def sleep_until(
    target: datetime,
    clock: Callable[[], datetime],
    sleeper: Callable[[float], None],
) -> None:
    while True:
        remaining = (target - clock()).total_seconds()
        if remaining <= 0:
            return
        sleeper(min(remaining, MAX_SLEEP_CHUNK_SECONDS))
