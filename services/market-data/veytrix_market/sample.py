"""Seeded weekday OHLCV for the SAMPLE instrument.

Prices are integer cents until they are converted to Decimal. The series is
synthetic. It is not a quote, a close, or a back-test of a listed security.
Weekend dates are omitted. Exchange holidays are not modelled.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

SAMPLE_DISCLAIMER = (
    "Synthetic sample. This is not a market price and not investment advice. Paper mode."
)
SOURCE_ID = "synthetic-sample"
SEED = 20261107
SERIES_START = date(2026, 1, 5)
TICK = Decimal("0.01")
_CENT = Decimal(100)


@dataclass(frozen=True)
class SampleInstrument:
    symbol: str
    venue: str
    asset_type: str
    currency: str
    source_id: str
    name: str
    timezone: str
    calendar: str
    tick_size: Decimal
    contract_multiplier: Decimal
    synthetic: bool = True

    def __post_init__(self) -> None:
        if self.symbol != "SAMPLE" or self.venue != "SIM":
            raise ValueError("The sample catalogue contains only SAMPLE at SIM.")
        if self.asset_type != "equity" or self.currency != "USD":
            raise ValueError("SAMPLE is a synthetic USD equity.")
        if self.source_id != SOURCE_ID or not self.synthetic:
            raise ValueError("SAMPLE must stay labelled as synthetic-sample.")


def sample_instrument() -> SampleInstrument:
    return SampleInstrument(
        symbol="SAMPLE",
        venue="SIM",
        asset_type="equity",
        currency="USD",
        source_id=SOURCE_ID,
        name="Synthetic sample equity",
        timezone="America/New_York",
        calendar="XNYS",
        tick_size=TICK,
        contract_multiplier=Decimal("1"),
    )


@dataclass(frozen=True)
class SampleBar:
    bar_start: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    source_id: str = SOURCE_ID

    def __post_init__(self) -> None:
        if self.bar_start.tzinfo is None or self.bar_start.utcoffset() != timedelta(0):
            raise ValueError("bar_start must be an aware UTC timestamp.")
        if self.bar_start.weekday() >= 5:
            raise ValueError("Sample bars are weekday sessions only.")
        if (
            self.bar_start.hour != 0
            or self.bar_start.minute != 0
            or self.bar_start.second != 0
            or self.bar_start.microsecond != 0
        ):
            raise ValueError("Daily sample bars start at 00:00:00Z.")
        for name in ("open", "high", "low", "close"):
            value = getattr(self, name)
            if isinstance(value, float) or not isinstance(value, Decimal):
                raise ValueError(f"{name} must be Decimal.")
            if value <= 0:
                raise ValueError(f"{name} must be positive.")
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close):
            raise ValueError("OHLC invariant failed.")
        if self.high < self.low:
            raise ValueError("High is below low.")
        if not isinstance(self.volume, int) or isinstance(self.volume, bool) or self.volume < 0:
            raise ValueError("Volume must be a non-negative integer.")
        if self.source_id != SOURCE_ID:
            raise ValueError("Sample bars must use the synthetic-sample source id.")


def weekday_sessions(count: int, start: date = SERIES_START) -> list[date]:
    if count < 1:
        raise ValueError("count must be at least 1.")
    if start.weekday() >= 5:
        raise ValueError("Series start must be a weekday.")
    sessions: list[date] = []
    cursor = start
    while len(sessions) < count:
        if cursor.weekday() < 5:
            sessions.append(cursor)
        cursor += timedelta(days=1)
    return sessions


def _bar_cents(rng: random.Random, previous_close_cents: int) -> tuple[int, int, int, int, int]:
    open_cents = previous_close_cents
    close_cents = max(500, open_cents + rng.randint(-180, 220))
    high_cents = max(open_cents, close_cents) + rng.randint(0, 90)
    low_cents = max(100, min(open_cents, close_cents) - rng.randint(0, 90))
    volume = rng.randint(50_000, 2_500_000)
    return open_cents, high_cents, low_cents, close_cents, volume


def _from_cents(cents: int) -> Decimal:
    return (Decimal(cents) / _CENT).quantize(TICK)


def generate_sample_bars(count: int = 120, seed: int = SEED) -> list[SampleBar]:
    """Return `count` deterministic daily bars beginning 2026-01-05."""

    if count < 1 or count > 252:
        raise ValueError("count must be between 1 and 252.")
    rng = random.Random(seed)
    close_cents = 10_000
    bars: list[SampleBar] = []
    for session in weekday_sessions(count):
        open_cents, high_cents, low_cents, close_cents, volume = _bar_cents(rng, close_cents)
        bars.append(
            SampleBar(
                bar_start=datetime(
                    session.year,
                    session.month,
                    session.day,
                    tzinfo=UTC,
                ),
                open=_from_cents(open_cents),
                high=_from_cents(high_cents),
                low=_from_cents(low_cents),
                close=_from_cents(close_cents),
                volume=volume,
            )
        )
    return bars
