"""Market-feed health stays a display. A down ticker does not grow a price."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient

from veytrix_api.main import create_app
from veytrix_market.coinbase import LiveTicker, QuoteUnavailable
from veytrix_market.health import age_seconds, classify_feed, overall_status

NOW = datetime(2026, 11, 9, 1, 0, tzinfo=UTC)
PRICES = {
    "BTC-USD": Decimal("75764.49"),
    "ETH-USD": Decimal("3200.10"),
    "SOL-USD": Decimal("180.25"),
}


def _ticker(symbol: str, retrieved_at: datetime) -> LiveTicker:
    return LiveTicker(
        price=PRICES[symbol],
        bid=PRICES[symbol],
        ask=PRICES[symbol],
        size=Decimal("1"),
        volume=Decimal("2"),
        trade_time="2026-11-09T00:59:00Z",
        trade_id=1,
        retrieved_at=retrieved_at,
    )


def test_a_print_at_the_stale_boundary_stays_up_and_one_second_later_is_stale() -> None:
    assert classify_feed(NOW - timedelta(seconds=120), NOW) == "up"
    assert classify_feed(NOW - timedelta(seconds=121), NOW) == "stale"
    assert age_seconds(NOW + timedelta(seconds=5), NOW) == 0
    assert overall_status(["up", "up", "up"]) == "ok"
    assert overall_status(["down", "down", "down"]) == "unavailable"
    assert overall_status(["up", "stale", "down"]) == "degraded"


def test_market_health_reports_each_feed_and_omits_a_down_price(monkeypatch) -> None:
    fresh = NOW - timedelta(seconds=30)
    stale = NOW - timedelta(seconds=121)
    calls: list[str] = []

    def fake_ticker(product_id: str) -> LiveTicker:
        calls.append(product_id)
        if product_id == "ETH-USD":
            raise QuoteUnavailable("down")
        if product_id == "SOL-USD":
            return _ticker(product_id, stale)
        return _ticker(product_id, fresh)

    monkeypatch.setattr("veytrix_api.routers.market.get_ticker", fake_ticker)
    monkeypatch.setattr("veytrix_api.routers.market.utc_now", lambda: NOW)
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/market/health")
        posted = client.post("/api/v1/market/health")

    body = response.json()
    assert response.status_code == 200
    assert posted.status_code == 405
    assert calls == ["BTC-USD", "ETH-USD", "SOL-USD"]
    assert body["status"] == "degraded"
    assert body["stale_after_seconds"] == 120
    assert body["sample_included"] is False
    assert body["executable"] is False
    assert body["execution_permitted"] is False
    assert body["order_submitted"] is False
    assert body["order_route"] == "absent"
    assert [feed["symbol"] for feed in body["feeds"]] == ["BTC-USD", "ETH-USD", "SOL-USD"]
    assert body["feeds"][0]["status"] == "up"
    assert body["feeds"][0]["price"] == "75764.49"
    assert body["feeds"][0]["age_seconds"] == 30
    assert body["feeds"][1]["status"] == "down"
    assert body["feeds"][1]["price"] is None
    assert body["feeds"][2]["status"] == "stale"
    assert body["feeds"][2]["price"] == "180.25"
    assert "3200.10" not in response.text
    assert "No order is sent" in body["note"]


def test_market_health_is_unavailable_when_every_feed_is_down(monkeypatch) -> None:
    def unavailable(product_id: str) -> LiveTicker:
        raise QuoteUnavailable(product_id)

    monkeypatch.setattr("veytrix_api.routers.market.get_ticker", unavailable)
    monkeypatch.setattr("veytrix_api.routers.market.utc_now", lambda: NOW)
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/market/health")

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "unavailable"
    assert [feed["status"] for feed in body["feeds"]] == ["down", "down", "down"]
    assert "75764.49" not in response.text
    assert "3200.10" not in response.text
    assert "180.25" not in response.text
