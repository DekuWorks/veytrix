"""Paper webhook adapters stay rejected. They do not call a broker."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from veytrix_api import signals


@pytest.fixture(autouse=True)
def _reset() -> None:
    signals.reset()
    yield
    signals.reset()


def test_adapters_are_disabled_until_configured() -> None:
    decision = signals.ingest(
        "traderspost",
        {"ticker": "AAPL", "action": "buy", "quantity": 1},
        strategy="mac01",
        account="paper",
    )
    assert decision["outcome"] == "rejected_disabled"
    assert decision["broker_called"] == "false"


def test_valid_invalid_duplicate_and_timeout() -> None:
    signals.adapters_enabled = True
    signals.set_route("mac01", "paper", "traderspost")
    now = datetime(2026, 11, 13, 15, tzinfo=UTC)
    payload = {
        "ticker": "AAPL",
        "action": "buy",
        "quantity": 1,
        "sent_at": now.isoformat(),
    }
    first = signals.ingest("traderspost", payload, strategy="mac01", account="paper", now=now)
    assert first["outcome"] == "rejected_broker"
    invalid = signals.ingest(
        "traderspost",
        {"ticker": "", "action": "hold", "quantity": 0},
        strategy="mac01",
        account="paper",
        now=now,
    )
    assert invalid["outcome"] == "rejected_payload"
    again = signals.ingest("traderspost", payload, strategy="mac01", account="paper", now=now)
    assert again["outcome"] == "rejected_duplicate"
    stale = {
        "ticker": "MSFT",
        "action": "sell",
        "quantity": 2,
        "sent_at": (now - timedelta(minutes=5)).isoformat(),
    }
    timed = signals.ingest("traderspost", stale, strategy="mac01", account="paper", now=now)
    assert timed["outcome"] == "rejected_timeout"


def test_one_route_rejects_the_other_provider() -> None:
    signals.adapters_enabled = True
    signals.set_route("mac01", "paper", "traderspost")
    other = signals.ingest(
        "signalstack",
        {"symbol": "AAPL", "side": "buy", "qty": 1},
        strategy="mac01",
        account="paper",
    )
    assert other["outcome"] == "rejected_route"
    signals.set_route("mac01", "paper", "signalstack")
    moved = signals.ingest(
        "traderspost",
        {"ticker": "AAPL", "action": "buy", "quantity": 1},
        strategy="mac01",
        account="paper",
    )
    assert moved["outcome"] == "rejected_route"
