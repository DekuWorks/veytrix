"""Pure SMA crossover on completed closes. Decimal only. No I/O."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

Side = Literal["BUY", "SELL", "HOLD"]


class InsufficientHistory(ValueError):
    """Fewer than slow_period + 1 completed closes."""


@dataclass(frozen=True)
class CrossoverSignal:
    side: Side
    reason: str
    fast_prev: Decimal
    slow_prev: Decimal
    fast_cur: Decimal
    slow_cur: Decimal


def _require_decimals(values: Sequence[Decimal]) -> None:
    for value in values:
        if not isinstance(value, Decimal) or not value.is_finite():
            raise TypeError("Closes must be finite Decimal values.")


def sma(values: Sequence[Decimal], period: int) -> Decimal:
    if period <= 0:
        raise ValueError("period must be positive.")
    if len(values) < period:
        raise InsufficientHistory(f"Need {period} closes, have {len(values)}.")
    window = values[-period:]
    _require_decimals(window)
    return sum(window, Decimal(0)) / Decimal(period)


def evaluate_crossover(
    closes: Sequence[Decimal], fast_period: int = 20, slow_period: int = 50
) -> CrossoverSignal:
    """BUY iff prev_fast <= prev_slow and cur_fast > cur_slow; SELL is the mirror; else HOLD."""

    if fast_period <= 0 or slow_period <= fast_period:
        raise ValueError("Require 0 < fast_period < slow_period.")
    if len(closes) < slow_period + 1:
        raise InsufficientHistory(f"Need {slow_period + 1} completed closes, have {len(closes)}.")
    _require_decimals(closes)
    previous = closes[:-1]
    fast_prev = sma(previous, fast_period)
    slow_prev = sma(previous, slow_period)
    fast_cur = sma(closes, fast_period)
    slow_cur = sma(closes, slow_period)
    if fast_prev <= slow_prev and fast_cur > slow_cur:
        side: Side = "BUY"
        reason = "fast SMA crossed above slow SMA"
    elif fast_prev >= slow_prev and fast_cur < slow_cur:
        side = "SELL"
        reason = "fast SMA crossed below slow SMA"
    else:
        side = "HOLD"
        reason = "no crossover"
    return CrossoverSignal(side, reason, fast_prev, slow_prev, fast_cur, slow_cur)


def rolling_sma(values: Sequence[Decimal], period: int) -> list[Decimal | None]:
    out: list[Decimal | None] = []
    running = Decimal(0)
    for index, value in enumerate(values):
        running += value
        if index >= period:
            running -= values[index - period]
        out.append(running / Decimal(period) if index >= period - 1 else None)
    return out


def crossover_markers(
    dates: Sequence[str], closes: Sequence[Decimal], fast_period: int, slow_period: int
) -> list[tuple[str, Side]]:
    """Every crossover in a completed series, using the same rule as `evaluate_crossover`."""

    markers: list[tuple[str, Side]] = []
    for end in range(slow_period + 1, len(closes) + 1):
        signal = evaluate_crossover(closes[:end], fast_period, slow_period)
        if signal.side != "HOLD":
            markers.append((dates[end - 1], signal.side))
    return markers
