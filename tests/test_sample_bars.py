from datetime import timedelta
from decimal import Decimal

from veytrix_market.sample import (
    SAMPLE_DISCLAIMER,
    SOURCE_ID,
    generate_sample_bars,
    sample_instrument,
)


def test_instrument_is_the_synthetic_sample_only() -> None:
    instrument = sample_instrument()

    assert instrument.symbol == "SAMPLE"
    assert instrument.venue == "SIM"
    assert instrument.asset_type == "equity"
    assert instrument.currency == "USD"
    assert instrument.source_id == SOURCE_ID
    assert instrument.synthetic is True
    assert "not a market price" in SAMPLE_DISCLAIMER
    assert "not investment advice" in SAMPLE_DISCLAIMER
    assert "Paper mode" in SAMPLE_DISCLAIMER


def test_bars_are_deterministic_weekday_sessions() -> None:
    first = generate_sample_bars(30)
    second = generate_sample_bars(30)
    longer = generate_sample_bars(60)

    assert first == second
    assert longer[:30] == first
    assert first[0].bar_start.date().isoformat() == "2026-01-05"
    assert first[0].bar_start.weekday() == 0
    assert first[0].bar_start.utcoffset() == timedelta(0)
    for bar in first:
        assert bar.bar_start.weekday() < 5
        assert bar.source_id == SOURCE_ID
        assert isinstance(bar.open, Decimal)
        assert bar.high >= max(bar.open, bar.close)
        assert bar.low <= min(bar.open, bar.close)
        assert bar.low > 0
        assert bar.volume > 0
        assert bar.open == bar.open.quantize(Decimal("0.01"))
