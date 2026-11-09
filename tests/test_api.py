import time
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient

from veytrix_api.db import get_db
from veytrix_api.deps import get_policy
from veytrix_api.main import create_app
from veytrix_api.ratelimit import (
    LOOPBACK_BURST,
    LOOPBACK_SUSTAINED_PER_MINUTE,
    ProcessLocalRateLimiter,
)
from veytrix_api.settings import DEFAULT_DATABASE_URL, Settings
from veytrix_market.coinbase import DailyBar, LiveTicker, QuoteSeries, QuoteUnavailable, clear_cache
from veytrix_market.sample import SAMPLE_DISCLAIMER
from veytrix_risk.sizing import DEFAULT_POLICY, STOPS_NOT_ENFORCED


class _RecordingSession:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.statements: list[str] = []

    def execute(self, statement, *_args, **_kwargs):
        self.statements.append(str(statement))
        if self.should_fail:
            raise RuntimeError("database down")
        return None


def _client(app=None) -> TestClient:
    return TestClient(app or create_app())


def test_health_does_not_require_a_database() -> None:
    settings = Settings(
        veytrix_env="local",
        veytrix_enable_live_broker=False,
        database_url="postgresql+psycopg://veytrix:local-dev-only@127.0.0.1:1/veytrix",
    )
    with _client(create_app(settings)) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_runs_select_one() -> None:
    app = create_app()
    session = _RecordingSession()

    def override():
        yield session

    app.dependency_overrides[get_db] = override
    with _client(app) as client:
        response = client.get("/api/v1/ready")

    assert response.status_code == 200
    assert response.json()["database"] == "up"
    assert "select 1" in session.statements[0].lower()


def test_ready_is_503_without_leaking_the_database_url() -> None:
    app = create_app()
    session = _RecordingSession(should_fail=True)

    def override():
        yield session

    app.dependency_overrides[get_db] = override
    with _client(app) as client:
        response = client.get("/api/v1/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "database": "down"}
    assert "local-dev-only" not in response.text
    assert DEFAULT_DATABASE_URL not in response.text


def test_diagnostics_reports_the_paper_posture_without_secrets() -> None:
    with _client() as client:
        response = client.get("/api/v1/diagnostics")

    body = response.json()
    assert response.status_code == 200
    assert body["trading_mode"] == "paper"
    assert body["live_broker"] == "disabled"
    assert body["auth"] == "not_configured"
    assert body["sample_data"] is True
    assert body["execution_permitted"] is False
    assert body["daily_weekly_stops_enforced"] is False
    assert body["rate_limit"] == "process_local"
    assert body["csrf"] == "not_implemented"
    assert body["versions"]["api"] == "0.1.0"
    assert "local-dev-only" not in response.text
    assert "database_url" not in response.text


def test_cors_allows_only_the_local_vite_origins() -> None:
    with _client() as client:
        allowed = client.get("/api/v1/health", headers={"Origin": "http://127.0.0.1:5173"})
        other_local = client.get("/api/v1/health", headers={"Origin": "http://localhost:5173"})
        rejected = client.get("/api/v1/health", headers={"Origin": "https://evil.example"})

    assert allowed.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
    assert other_local.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert allowed.headers.get("access-control-allow-credentials") != "true"
    assert "access-control-allow-origin" not in rejected.headers


def test_correlation_id_is_echoed_or_replaced() -> None:
    with _client() as client:
        kept = client.get("/api/v1/health", headers={"X-Correlation-ID": "abc-123"})
        replaced = client.get("/api/v1/health", headers={"X-Correlation-ID": "bad id\n"})

    assert kept.headers["x-correlation-id"] == "abc-123"
    generated = replaced.headers["x-correlation-id"]
    assert generated != "bad id\n"
    assert " " not in generated
    assert len(generated) <= 64


def test_rate_limit_is_process_local_and_health_stays_open() -> None:
    settings = Settings(
        veytrix_env="local",
        veytrix_enable_live_broker=False,
        database_url=DEFAULT_DATABASE_URL,
        rate_limit_per_minute=2,
    )
    with _client(create_app(settings)) as client:
        assert client.get("/api/v1/diagnostics").status_code == 200
        assert client.get("/api/v1/diagnostics").status_code == 200
        blocked = client.get("/api/v1/diagnostics")
        health = client.get("/api/v1/health")

    assert blocked.status_code == 429
    assert "process-local" in blocked.json()["detail"]
    assert health.status_code == 200


def test_market_page_burst_is_allowed_before_a_tighter_loop_is_rejected() -> None:
    """Ticker + 1-minute bars + daily bars, then the same three for a product switch."""

    market_load = 3
    clock = {"now": 0.0}
    limiter = ProcessLocalRateLimiter(
        LOOPBACK_SUSTAINED_PER_MINUTE,
        clock=lambda: clock["now"],
        burst=LOOPBACK_BURST,
    )

    for _ in range(market_load + market_load):
        allowed, _remaining = limiter.check("127.0.0.1")
        assert allowed is True

    for _ in range(LOOPBACK_BURST - (market_load + market_load)):
        assert limiter.check("127.0.0.1")[0] is True
    assert limiter.check("127.0.0.1")[0] is False

    clock["now"] += 1.0
    refilled = 0
    for _ in range(LOOPBACK_BURST):
        if not limiter.check("127.0.0.1")[0]:
            break
        refilled += 1
    assert refilled == LOOPBACK_SUSTAINED_PER_MINUTE // 60

    settings = Settings(
        veytrix_env="local",
        veytrix_enable_live_broker=False,
        database_url=DEFAULT_DATABASE_URL,
        rate_limit_per_minute=LOOPBACK_SUSTAINED_PER_MINUTE,
    )
    with _client(create_app(settings)) as client:
        statuses = [
            client.get("/api/v1/diagnostics").status_code for _ in range(market_load + market_load)
        ]
    assert statuses == [200, 200, 200, 200, 200, 200]


def test_sample_market_routes_do_not_invent_another_symbol() -> None:
    with _client() as client:
        instruments = client.get("/api/v1/market/instruments")
        bars = client.get("/api/v1/market/instruments/SAMPLE/bars?limit=5")
        again = client.get("/api/v1/market/instruments/SAMPLE/bars?limit=5")
        missing = client.get("/api/v1/market/instruments/AAPL/bars")

    catalogue = {item["symbol"]: item for item in instruments.json()["instruments"]}
    assert instruments.status_code == 200
    assert set(catalogue) == {"BTC-USD", "ETH-USD", "SOL-USD", "SAMPLE"}
    assert catalogue["SAMPLE"]["source_id"] == "synthetic-sample"
    assert catalogue["SAMPLE"]["venue"] == "SIM"
    assert catalogue["SAMPLE"]["synthetic"] is True
    assert catalogue["BTC-USD"]["synthetic"] is False
    assert catalogue["BTC-USD"]["source_id"] == "coinbase-exchange"
    assert catalogue["ETH-USD"]["synthetic"] is False
    assert catalogue["ETH-USD"]["source_id"] == "coinbase-exchange"
    assert catalogue["ETH-USD"]["venue"] == "COINBASE"
    assert catalogue["ETH-USD"]["name"] == "Ether / US dollar"
    assert catalogue["SOL-USD"]["synthetic"] is False
    assert catalogue["SOL-USD"]["source_id"] == "coinbase-exchange"
    assert catalogue["SOL-USD"]["venue"] == "COINBASE"
    assert catalogue["SOL-USD"]["name"] == "Solana / US dollar"
    assert "SAMPLE is synthetic" in instruments.json()["disclaimer"]
    assert bars.status_code == 200
    assert bars.json() == again.json()
    assert bars.json()["synthetic"] is True
    assert bars.json()["source_id"] == "synthetic-sample"
    assert bars.json()["disclaimer"] == SAMPLE_DISCLAIMER
    assert bars.json()["bars"][0]["bar_start"].endswith("Z")
    assert isinstance(bars.json()["bars"][0]["volume"], str)
    assert len(bars.json()["bars"]) == 5
    assert missing.status_code == 404


def test_btc_bars_use_the_coinbase_series_and_fail_closed(monkeypatch) -> None:
    clear_cache()
    series = QuoteSeries(
        bars=(
            DailyBar(
                bar_start=datetime(2026, 11, 7, tzinfo=UTC),
                open=Decimal("74500.10"),
                high=Decimal("76000.00"),
                low=Decimal("74000.00"),
                close=Decimal("75000.00"),
                volume=Decimal("10.5"),
            ),
            DailyBar(
                bar_start=datetime(2026, 11, 8, tzinfo=UTC),
                open=Decimal("75753.95"),
                high=Decimal("75830.11"),
                low=Decimal("75545.34"),
                close=Decimal("75767.33"),
                volume=Decimal("260.19458529"),
            ),
        ),
        retrieved_at=datetime(2026, 11, 8, 3, 0, tzinfo=UTC),
    )

    def fake_series(product_id: str, limit: int) -> QuoteSeries:
        assert product_id == "BTC-USD"
        assert limit == 2
        return series

    monkeypatch.setattr("veytrix_api.routers.market.get_daily", fake_series)
    with _client() as client:
        response = client.get("/api/v1/market/instruments/BTC-USD/bars?limit=2")

    body = response.json()
    assert response.status_code == 200
    assert body["synthetic"] is False
    assert body["last_close"] == "75767.33"
    assert body["previous_close"] == "75000.00"
    assert body["change"] == "+767.33"
    assert body["change_percent"] == "+1.02"
    assert body["bars"][1]["volume"] == "260.19458529"
    assert "not investment advice" in body["disclaimer"]

    def unavailable(product_id: str, limit: int) -> QuoteSeries:
        raise QuoteUnavailable("down")

    monkeypatch.setattr("veytrix_api.routers.market.get_daily", unavailable)
    with _client() as client:
        failed = client.get("/api/v1/market/instruments/BTC-USD/bars?limit=2")

    assert failed.status_code == 502
    assert "No substitute prices" in failed.json()["detail"]
    assert "75767.33" not in failed.text


def test_btc_minute_bars_use_coinbase_and_fail_closed(monkeypatch) -> None:
    clear_cache()
    series = QuoteSeries(
        bars=(
            DailyBar(
                bar_start=datetime(2026, 11, 8, 3, 58, tzinfo=UTC),
                open=Decimal("75802.00"),
                high=Decimal("75810.00"),
                low=Decimal("75790.00"),
                close=Decimal("75800.00"),
                volume=Decimal("1.25"),
            ),
            DailyBar(
                bar_start=datetime(2026, 11, 8, 3, 59, tzinfo=UTC),
                open=Decimal("75800.00"),
                high=Decimal("75820.00"),
                low=Decimal("75795.00"),
                close=Decimal("75805.98"),
                volume=Decimal("2.5"),
            ),
        ),
        retrieved_at=datetime(2026, 11, 8, 3, 59, 8, tzinfo=UTC),
    )

    def fake_series(product_id: str, limit: int) -> QuoteSeries:
        assert product_id == "BTC-USD"
        assert limit == 180
        return series

    monkeypatch.setattr("veytrix_api.routers.market.get_minute", fake_series)
    with _client() as client:
        response = client.get("/api/v1/market/instruments/BTC-USD/bars?interval=1m&limit=180")
        sample = client.get("/api/v1/market/instruments/SAMPLE/bars?interval=1m&limit=5")

    body = response.json()
    assert response.status_code == 200
    assert body["interval"] == "1m"
    assert body["synthetic"] is False
    assert body["source_id"] == "coinbase-exchange"
    assert body["last_close"] == "75805.98"
    assert body["bars"][0]["bar_start"] == "2026-11-08T03:58:00Z"
    assert "1-minute" in body["disclaimer"]
    assert "Not a consolidated quote" in body["disclaimer"]
    assert "No order is sent" in body["disclaimer"]
    assert sample.status_code == 422

    def unavailable(product_id: str, limit: int) -> QuoteSeries:
        raise QuoteUnavailable("down")

    monkeypatch.setattr("veytrix_api.routers.market.get_minute", unavailable)
    with _client() as client:
        failed = client.get("/api/v1/market/instruments/BTC-USD/bars?interval=1m&limit=180")

    assert failed.status_code == 502
    assert "No substitute prices" in failed.json()["detail"]
    assert "75805.98" not in failed.text


def test_btc_ticker_returns_the_live_print_and_fails_closed(monkeypatch) -> None:
    clear_cache()
    ticker = LiveTicker(
        price=Decimal("75764.49"),
        bid=Decimal("75764.49"),
        ask=Decimal("75764.50"),
        size=Decimal("0.00000011"),
        volume=Decimal("2022.50285353"),
        trade_time="2026-11-08T03:55:44.792670175Z",
        trade_id=1116967290,
        retrieved_at=datetime(2026, 11, 8, 3, 55, tzinfo=UTC),
    )

    def fake_ticker(product_id: str) -> LiveTicker:
        assert product_id == "BTC-USD"
        return ticker

    monkeypatch.setattr("veytrix_api.routers.market.get_ticker", fake_ticker)
    with _client() as client:
        response = client.get("/api/v1/market/instruments/BTC-USD/ticker")
        missing = client.get("/api/v1/market/instruments/SAMPLE/ticker")

    body = response.json()
    assert response.status_code == 200
    assert body["symbol"] == "BTC-USD"
    assert body["synthetic"] is False
    assert body["price"] == "75764.49"
    assert body["bid"] == "75764.49"
    assert body["ask"] == "75764.50"
    assert body["trade_id"] == 1116967290
    assert body["trade_time"].startswith("2026-11-08T03:55:44")
    assert "BTC-USD" in body["disclaimer"]
    assert "No order is sent" in body["disclaimer"]
    assert missing.status_code == 404

    def unavailable(product_id: str) -> LiveTicker:
        raise QuoteUnavailable("down")

    monkeypatch.setattr("veytrix_api.routers.market.get_ticker", unavailable)
    with _client() as client:
        failed = client.get("/api/v1/market/instruments/BTC-USD/ticker")

    assert failed.status_code == 502
    assert "No substitute price" in failed.json()["detail"]
    assert "75764.49" not in failed.text


def test_eth_routes_use_the_shared_coinbase_parser_and_fail_closed(monkeypatch) -> None:
    clear_cache()
    series = QuoteSeries(
        bars=(
            DailyBar(
                bar_start=datetime(2026, 11, 7, tzinfo=UTC),
                open=Decimal("3100.00"),
                high=Decimal("3200.00"),
                low=Decimal("3050.00"),
                close=Decimal("3160.00"),
                volume=Decimal("1200.5"),
            ),
            DailyBar(
                bar_start=datetime(2026, 11, 8, tzinfo=UTC),
                open=Decimal("3160.00"),
                high=Decimal("3250.00"),
                low=Decimal("3150.10"),
                close=Decimal("3210.55"),
                volume=Decimal("980.25"),
            ),
        ),
        retrieved_at=datetime(2026, 11, 8, 4, 12, tzinfo=UTC),
    )
    minute = QuoteSeries(
        bars=(
            DailyBar(
                bar_start=datetime(2026, 11, 8, 4, 11, tzinfo=UTC),
                open=Decimal("3208.00"),
                high=Decimal("3212.00"),
                low=Decimal("3206.00"),
                close=Decimal("3208.10"),
                volume=Decimal("12.5"),
            ),
        ),
        retrieved_at=datetime(2026, 11, 8, 4, 12, tzinfo=UTC),
    )
    ticker = LiveTicker(
        price=Decimal("3210.55"),
        bid=Decimal("3210.50"),
        ask=Decimal("3210.60"),
        size=Decimal("0.42"),
        volume=Decimal("12345.6"),
        trade_time="2026-11-08T04:11:59.100000Z",
        trade_id=88001122,
        retrieved_at=datetime(2026, 11, 8, 4, 12, tzinfo=UTC),
    )

    def fake_daily(product_id: str, limit: int) -> QuoteSeries:
        assert product_id == "ETH-USD"
        assert limit == 2
        return series

    def fake_minute(product_id: str, limit: int) -> QuoteSeries:
        assert product_id == "ETH-USD"
        assert limit == 180
        return minute

    def fake_ticker(product_id: str) -> LiveTicker:
        assert product_id == "ETH-USD"
        return ticker

    monkeypatch.setattr("veytrix_api.routers.market.get_daily", fake_daily)
    monkeypatch.setattr("veytrix_api.routers.market.get_minute", fake_minute)
    monkeypatch.setattr("veytrix_api.routers.market.get_ticker", fake_ticker)
    with _client() as client:
        daily = client.get("/api/v1/market/instruments/ETH-USD/bars?limit=2")
        intraday = client.get("/api/v1/market/instruments/ETH-USD/bars?interval=1m&limit=180")
        live = client.get("/api/v1/market/instruments/ETH-USD/ticker")
        unknown = client.get("/api/v1/market/instruments/DOGE-USD/ticker")

    daily_body = daily.json()
    assert daily.status_code == 200
    assert daily_body["symbol"] == "ETH-USD"
    assert daily_body["synthetic"] is False
    assert daily_body["source_id"] == "coinbase-exchange"
    assert daily_body["last_close"] == "3210.55"
    assert daily_body["previous_close"] == "3160.00"
    assert daily_body["source_url"] == "https://api.exchange.coinbase.com/products/ETH-USD/candles"
    assert "ETH-USD" in daily_body["disclaimer"]
    assert "BTC-USD" not in daily_body["disclaimer"]
    assert "Not a consolidated quote" in daily_body["disclaimer"]
    assert "not investment advice" in daily_body["disclaimer"]
    assert "No order is sent" in daily_body["disclaimer"]

    minute_body = intraday.json()
    assert intraday.status_code == 200
    assert minute_body["symbol"] == "ETH-USD"
    assert minute_body["interval"] == "1m"
    assert minute_body["last_close"] == "3208.10"
    assert "ETH-USD" in minute_body["disclaimer"]
    assert "1-minute" in minute_body["disclaimer"]
    assert "Not a consolidated quote" in minute_body["disclaimer"]
    assert "No order is sent" in minute_body["disclaimer"]

    live_body = live.json()
    assert live.status_code == 200
    assert live_body["symbol"] == "ETH-USD"
    assert live_body["price"] == "3210.55"
    assert live_body["bid"] == "3210.50"
    assert live_body["ask"] == "3210.60"
    assert live_body["trade_time"].startswith("2026-11-08T04:11:59")
    assert "ETH-USD" in live_body["disclaimer"]
    assert "No order is sent" in live_body["disclaimer"]
    assert unknown.status_code == 404

    def unavailable(*_args: object, **_kwargs: object) -> QuoteSeries:
        raise QuoteUnavailable("down")

    monkeypatch.setattr("veytrix_api.routers.market.get_daily", unavailable)
    monkeypatch.setattr("veytrix_api.routers.market.get_minute", unavailable)
    monkeypatch.setattr("veytrix_api.routers.market.get_ticker", unavailable)
    with _client() as client:
        failed_daily = client.get("/api/v1/market/instruments/ETH-USD/bars?limit=2")
        failed_minute = client.get("/api/v1/market/instruments/ETH-USD/bars?interval=1m&limit=180")
        failed_ticker = client.get("/api/v1/market/instruments/ETH-USD/ticker")

    for failed in (failed_daily, failed_minute, failed_ticker):
        assert failed.status_code == 502
        assert "3210.55" not in failed.text
        assert "3208.10" not in failed.text
        assert "75764.49" not in failed.text
    assert "No substitute prices" in failed_daily.json()["detail"]
    assert "No substitute price" in failed_ticker.json()["detail"]


def test_sol_routes_use_the_shared_coinbase_parser_and_fail_closed(monkeypatch) -> None:
    series = QuoteSeries(
        bars=(
            DailyBar(
                bar_start=datetime(2026, 11, 7, tzinfo=UTC),
                open=Decimal("180.00"),
                high=Decimal("188.00"),
                low=Decimal("178.50"),
                close=Decimal("184.20"),
                volume=Decimal("900.5"),
            ),
            DailyBar(
                bar_start=datetime(2026, 11, 8, tzinfo=UTC),
                open=Decimal("184.20"),
                high=Decimal("190.00"),
                low=Decimal("183.10"),
                close=Decimal("186.40"),
                volume=Decimal("1100.25"),
            ),
        ),
        retrieved_at=datetime(2026, 11, 8, 5, 20, tzinfo=UTC),
    )
    minute = QuoteSeries(
        bars=(
            DailyBar(
                bar_start=datetime(2026, 11, 8, 5, 19, tzinfo=UTC),
                open=Decimal("186.10"),
                high=Decimal("186.80"),
                low=Decimal("185.90"),
                close=Decimal("186.42"),
                volume=Decimal("40.5"),
            ),
        ),
        retrieved_at=datetime(2026, 11, 8, 5, 20, tzinfo=UTC),
    )
    ticker = LiveTicker(
        price=Decimal("186.40"),
        bid=Decimal("186.39"),
        ask=Decimal("186.41"),
        size=Decimal("3.2"),
        volume=Decimal("88000.1"),
        trade_time="2026-11-08T05:19:40.000000Z",
        trade_id=99001122,
        retrieved_at=datetime(2026, 11, 8, 5, 20, tzinfo=UTC),
    )

    def fake_daily(product_id: str, limit: int) -> QuoteSeries:
        assert product_id == "SOL-USD"
        assert limit == 14
        return series

    def fake_minute(product_id: str, limit: int) -> QuoteSeries:
        assert product_id == "SOL-USD"
        assert limit == 180
        return minute

    def fake_ticker(product_id: str) -> LiveTicker:
        assert product_id == "SOL-USD"
        return ticker

    monkeypatch.setattr("veytrix_api.routers.market.get_daily", fake_daily)
    monkeypatch.setattr("veytrix_api.routers.market.get_minute", fake_minute)
    monkeypatch.setattr("veytrix_api.routers.market.get_ticker", fake_ticker)
    with _client() as client:
        daily = client.get("/api/v1/market/instruments/SOL-USD/bars?interval=1d&limit=14")
        intraday = client.get("/api/v1/market/instruments/SOL-USD/bars?interval=1m&limit=180")
        live = client.get("/api/v1/market/instruments/SOL-USD/ticker")
        unknown = client.get("/api/v1/market/instruments/DOGE-USD/bars")

    assert daily.status_code == 200
    assert daily.json()["symbol"] == "SOL-USD"
    assert daily.json()["last_close"] == "186.40"
    assert (
        daily.json()["source_url"] == "https://api.exchange.coinbase.com/products/SOL-USD/candles"
    )
    assert "SOL-USD" in daily.json()["disclaimer"]
    assert "Not a consolidated quote" in daily.json()["disclaimer"]
    assert "No order is sent" in daily.json()["disclaimer"]
    assert intraday.status_code == 200
    assert intraday.json()["interval"] == "1m"
    assert intraday.json()["last_close"] == "186.42"
    assert "1-minute" in intraday.json()["disclaimer"]
    assert live.status_code == 200
    assert live.json()["price"] == "186.40"
    assert live.json()["bid"] == "186.39"
    assert live.json()["ask"] == "186.41"
    assert "SOL-USD" in live.json()["disclaimer"]
    assert "No order is sent" in live.json()["disclaimer"]
    assert unknown.status_code == 404

    def unavailable(*_args: object, **_kwargs: object) -> QuoteSeries:
        raise QuoteUnavailable("down")

    monkeypatch.setattr("veytrix_api.routers.market.get_daily", unavailable)
    monkeypatch.setattr("veytrix_api.routers.market.get_minute", unavailable)
    monkeypatch.setattr("veytrix_api.routers.market.get_ticker", unavailable)
    with _client() as client:
        failed_daily = client.get("/api/v1/market/instruments/SOL-USD/bars?limit=2")
        failed_minute = client.get("/api/v1/market/instruments/SOL-USD/bars?interval=1m&limit=180")
        failed_ticker = client.get("/api/v1/market/instruments/SOL-USD/ticker")

    for failed in (failed_daily, failed_minute, failed_ticker):
        assert failed.status_code == 502
        assert "186.40" not in failed.text
        assert "186.42" not in failed.text
    assert "No substitute prices" in failed_daily.json()["detail"]
    assert "No substitute price" in failed_ticker.json()["detail"]


def _statement_limit(statement: object) -> int | None:
    clause = getattr(statement, "_limit_clause", None)
    if clause is None:
        return None
    value = getattr(clause, "value", None)
    if isinstance(value, int):
        return value
    inner = getattr(value, "value", None)
    if isinstance(inner, int):
        return inner
    return None


class _JournalSession:
    """In-memory journal. Tests never commit a row to the dev database."""

    def __init__(self) -> None:
        self.rows: list[Any] = []
        self.events: list[Any] = []

    def add(self, row: Any) -> None:
        name = type(row).__name__
        if name == "AuditEvent":
            if row.action != "risk.size.recorded":
                raise AssertionError(row.action)
            if row.payload.get("execution_permitted") is not False:
                raise AssertionError("audit row permitted execution")
            if row.payload.get("order_submitted") is not False:
                raise AssertionError("audit row submitted an order")
            self.events.append(row)
            return
        if name != "PaperSizeJournalRow":
            raise AssertionError(f"unexpected row {name}")
        self.rows.append(row)

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None

    def scalars(self, statement: object) -> list[Any]:
        rows = sorted(self.rows, key=lambda row: (row.recorded_at, str(row.id)), reverse=True)
        limit = _statement_limit(statement)
        if limit is not None:
            return rows[:limit]
        return rows


def _journal_db(session: _JournalSession):
    def override():
        yield session

    return override


def _size_body(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "symbol": "BTC-USD",
        "account_equity": "100000.00",
        "entry_price": "50.00",
        "stop_price": "48.00",
        "side": "long",
    }
    body.update(overrides)
    return body


def test_size_endpoint_calculates_and_does_not_order() -> None:
    app = create_app()
    session = _JournalSession()
    app.dependency_overrides[get_policy] = lambda: DEFAULT_POLICY
    app.dependency_overrides[get_db] = _journal_db(session)
    with _client(app) as client:
        response = client.post(
            "/api/v1/risk/size",
            json=_size_body(),
            headers={"X-Correlation-ID": "size-audit-1"},
        )
        rejected = client.post("/api/v1/risk/size", json=_size_body(risk_fraction="0.03"))
        number = client.post(
            "/api/v1/risk/size",
            json={"account_equity": 100000, "entry_price": "50.00", "stop_price": "48.00"},
        )
        extra = client.post("/api/v1/risk/size", json=_size_body(submit_order=True))

    body = response.json()
    assert response.status_code == 200
    assert body["symbol"] == "BTC-USD"
    assert body["shares"] == 200
    assert body["binding_constraint"] == "allocation"
    assert Decimal(body["planned_risk_amount"]) == Decimal("400.00")
    assert body["execution_permitted"] is False
    assert body["order_submitted"] is False
    assert body["daily_stop_enforced"] is False
    assert body["weekly_stop_enforced"] is False
    assert body["note"] == STOPS_NOT_ENFORCED
    assert "order_id" not in body
    assert rejected.status_code == 422
    assert number.status_code == 422
    assert extra.status_code == 422
    assert len(session.rows) == 1
    assert session.rows[0].execution_permitted is False
    assert session.rows[0].order_submitted is False
    assert len(session.events) == 1
    assert session.events[0].correlation_id == "size-audit-1"
    assert session.events[0].payload["symbol"] == "BTC-USD"
    assert session.events[0].payload["shares"] == 200
    assert session.events[0].payload["execution_permitted"] is False
    assert session.events[0].payload["order_submitted"] is False
    assert "account_equity" not in session.events[0].payload
    paths = app.openapi()["paths"]
    order_paths = {path for path in paths if "order" in path}
    assert order_paths <= {
        "/api/v1/strategies/mac-01/orders",
        "/api/v1/paper-swaps/orders",
    }
    for path in order_paths:
        assert set(paths[path]) == {"get"}, "order ledgers are read-only"


def test_size_journal_records_a_success_and_skips_a_rejection() -> None:
    app = create_app()
    session = _JournalSession()
    app.dependency_overrides[get_policy] = lambda: DEFAULT_POLICY
    app.dependency_overrides[get_db] = _journal_db(session)
    with _client(app) as client:
        rejected = client.post("/api/v1/risk/size", json=_size_body(stop_price="50.00"))
        unknown = client.post("/api/v1/risk/size", json=_size_body(symbol="DOGE-USD"))
        created = client.post("/api/v1/risk/size", json=_size_body(symbol="ETH-USD"))
        time.sleep(0.01)
        later = client.post(
            "/api/v1/risk/size",
            json=_size_body(symbol="SOL-USD", entry_price="90.00", stop_price="88.00"),
        )
        listed = client.get("/api/v1/audit/size-journal")
        removed = client.delete("/api/v1/audit/size-journal")
        removed_one = client.delete(f"/api/v1/audit/size-journal/{created.json()['symbol']}")

    assert rejected.status_code == 422
    assert unknown.status_code == 422
    assert created.status_code == 200
    assert session.rows[0].symbol == "ETH-USD"
    assert created.json()["execution_permitted"] is False
    assert created.json()["order_submitted"] is False
    assert later.status_code == 200
    assert len(session.rows) == 2
    assert listed.status_code == 200
    entries = listed.json()["entries"]
    assert [item["symbol"] for item in entries] == ["SOL-USD", "ETH-USD"]
    assert entries[0]["execution_permitted"] is False
    assert entries[0]["order_submitted"] is False
    assert "order_id" not in entries[0]
    assert "broker_id" not in entries[0]
    assert Decimal(entries[1]["equity"]) == Decimal("100000.00")
    assert Decimal(entries[1]["entry"]) == Decimal("50.00")
    assert Decimal(entries[1]["stop"]) == Decimal("48.00")
    assert entries[1]["shares"] == 200
    assert entries[1]["binding_constraint"] == "allocation"
    assert Decimal(entries[1]["planned_risk"]) == Decimal("400.00")
    assert removed.status_code == 405
    assert removed_one.status_code == 404
    assert len(session.events) == 2
    assert all(event.payload["order_submitted"] is False for event in session.events)
    assert "/api/v1/audit/size-journal/{entry_id}" not in app.openapi()["paths"]
    methods = set(app.openapi()["paths"]["/api/v1/audit/size-journal"])
    assert methods == {"get"}
    assert len(session.rows) == 2


def test_size_journal_returns_the_newest_twenty_without_sizing(monkeypatch) -> None:
    from uuid import UUID

    from veytrix_api.models import PaperSizeJournalRow

    calls = {"size": 0}

    def counted_size(*_args: object, **_kwargs: object) -> None:
        calls["size"] += 1
        raise AssertionError("size calculator was called")

    monkeypatch.setattr("veytrix_api.routers.risk.size_position", counted_size)
    monkeypatch.setattr("veytrix_risk.sizing.size_position", counted_size)
    app = create_app()
    session = _JournalSession()
    base = datetime(2026, 11, 8, 4, 0, tzinfo=UTC)
    for index in range(21):
        session.rows.append(
            PaperSizeJournalRow(
                id=UUID(int=index),
                recorded_at=base.replace(minute=index),
                symbol="BTC-USD",
                equity=Decimal("100000.00"),
                entry=Decimal("50.00"),
                stop=Decimal("48.00"),
                shares=index,
                planned_risk=Decimal("400.00"),
                binding_constraint="allocation",
                execution_permitted=False,
                order_submitted=False,
            )
        )
    app.dependency_overrides[get_db] = _journal_db(session)
    with _client(app) as client:
        listed = client.get("/api/v1/audit/size-journal")
        missing = client.delete("/api/v1/audit/size-journal")

    assert listed.status_code == 200
    entries = listed.json()["entries"]
    assert len(entries) == 20
    assert entries[0]["shares"] == 20
    assert entries[-1]["shares"] == 1
    assert all(item["shares"] != 0 for item in entries)
    assert calls["size"] == 0
    assert missing.status_code == 405
    assert len(session.rows) == 21


class _PaperSession:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.rows: list[Any] = []

    def add(self, row: Any) -> None:
        if self.should_fail:
            raise RuntimeError("database down")
        self.rows.append(row)

    def commit(self) -> None:
        if self.should_fail:
            raise RuntimeError("database down")

    def rollback(self) -> None:
        return None

    def get(self, _model: object, key: object) -> Any | None:
        if self.should_fail:
            raise RuntimeError("database down")
        for row in self.rows:
            if row.id == key:
                return row
        return None

    def delete(self, row: Any) -> None:
        self.rows.remove(row)

    def scalars(self, _statement: object) -> list[Any]:
        if self.should_fail:
            raise RuntimeError("database down")
        return sorted(self.rows, key=lambda row: row.recorded_at, reverse=True)


def _paper_body() -> dict[str, object]:
    return {
        "symbol": "ETH-USD",
        "entry": "2233.58",
        "stop": "2200.00",
        "shares": 4,
        "notional": "8934.32",
        "planned_risk": "134.32",
        "binding_constraint": "allocation",
        "exchange_time": "2026-11-08T04:21:04.000000Z",
    }


def test_paper_position_is_stored_without_an_order() -> None:
    app = create_app()
    session = _PaperSession()

    def override():
        yield session

    app.dependency_overrides[get_db] = override
    with _client(app) as client:
        created = client.post("/api/v1/portfolio/positions", json=_paper_body())
        listed = client.get("/api/v1/portfolio/positions")
        removed = client.delete(f"/api/v1/portfolio/positions/{created.json()['id']}")
        after = client.get("/api/v1/portfolio/positions")
        missing = client.delete(f"/api/v1/portfolio/positions/{created.json()['id']}")

    body = created.json()
    assert created.status_code == 200
    assert body["symbol"] == "ETH-USD"
    assert Decimal(body["entry"]) == Decimal("2233.58")
    assert Decimal(body["stop"]) == Decimal("2200.00")
    assert body["shares"] == 4
    assert Decimal(body["notional"]) == Decimal("8934.32")
    assert Decimal(body["planned_risk"]) == Decimal("134.32")
    assert body["binding_constraint"] == "allocation"
    assert body["exchange_time"] == "2026-11-08T04:21:04Z"
    assert body["recorded_at"].endswith("Z")
    assert body["execution_permitted"] is False
    assert body["order_submitted"] is False
    assert "order_id" not in body
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["positions"]] == [body["id"]]
    assert removed.status_code == 204
    assert after.status_code == 200
    assert after.json()["positions"] == []
    assert missing.status_code == 404


def test_paper_position_rejects_floats_extra_fields_and_other_symbols() -> None:
    app = create_app()
    session = _PaperSession(should_fail=True)

    def override():
        yield session

    app.dependency_overrides[get_db] = override
    floated = _paper_body()
    floated["entry"] = 2233.58
    extra = _paper_body()
    extra["order_id"] = "nope"
    other = _paper_body()
    other["symbol"] = "AAPL"
    with _client(app) as client:
        number = client.post("/api/v1/portfolio/positions", json=floated)
        surplus = client.post("/api/v1/portfolio/positions", json=extra)
        equity = client.post("/api/v1/portfolio/positions", json=other)
        down = client.get("/api/v1/portfolio/positions")

    assert number.status_code == 422
    assert surplus.status_code == 422
    assert equity.status_code == 422
    assert down.status_code == 503
    assert down.json()["detail"] == "Paper position store is unavailable."
    assert session.rows == []


def test_paper_position_accepts_sol_and_rejects_other_symbols() -> None:
    app = create_app()
    session = _PaperSession()

    def override():
        yield session

    app.dependency_overrides[get_db] = override
    sol = _paper_body()
    sol["symbol"] = "SOL-USD"
    sol["entry"] = "186.40"
    sol["stop"] = "180.00"
    sol["shares"] = 50
    sol["notional"] = "9320.00"
    sol["planned_risk"] = "320.00"
    other = _paper_body()
    other["symbol"] = "DOGE-USD"
    with _client(app) as client:
        created = client.post("/api/v1/portfolio/positions", json=sol)
        rejected = client.post("/api/v1/portfolio/positions", json=other)

    body = created.json()
    assert created.status_code == 200
    assert body["symbol"] == "SOL-USD"
    assert Decimal(body["entry"]) == Decimal("186.40")
    assert body["execution_permitted"] is False
    assert body["order_submitted"] is False
    assert "order_id" not in body
    assert rejected.status_code == 422
    assert len(session.rows) == 1


class _NoteSession:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.rows: list[Any] = []

    def add(self, row: Any) -> None:
        if self.should_fail:
            raise RuntimeError("database down")
        self.rows.append(row)

    def commit(self) -> None:
        if self.should_fail:
            raise RuntimeError("database down")

    def rollback(self) -> None:
        return None

    def get(self, _model: object, key: object) -> Any | None:
        if self.should_fail:
            raise RuntimeError("database down")
        for row in self.rows:
            if row.id == key:
                return row
        return None

    def delete(self, row: Any) -> None:
        self.rows.remove(row)

    def scalars(self, _statement: object) -> list[Any]:
        if self.should_fail:
            raise RuntimeError("database down")
        return sorted(self.rows, key=lambda row: (row.created_at, str(row.id)), reverse=True)


def test_research_note_is_stored_without_an_order() -> None:
    app = create_app()
    session = _NoteSession()

    def override():
        yield session

    app.dependency_overrides[get_db] = override
    with _client(app) as client:
        older = client.post(
            "/api/v1/research/notes",
            json={"title": "First", "body": "Older observation."},
        )
        time.sleep(0.01)
        newer = client.post(
            "/api/v1/research/notes",
            json={"title": "Desk check", "body": "Newer observation."},
        )
        listed = client.get("/api/v1/research/notes")
        removed = client.delete(f"/api/v1/research/notes/{newer.json()['id']}")
        after = client.get("/api/v1/research/notes")
        missing = client.delete(f"/api/v1/research/notes/{newer.json()['id']}")

    first = older.json()
    second = newer.json()
    assert older.status_code == 200
    assert newer.status_code == 200
    assert second["title"] == "Desk check"
    assert second["body"] == "Newer observation."
    assert second["created_at"].endswith("Z")
    assert "symbol" not in second
    assert "order_id" not in second
    assert listed.status_code == 200
    notes = listed.json()["notes"]
    assert [item["id"] for item in notes] == [second["id"], first["id"]]
    assert notes[0]["created_at"] >= notes[1]["created_at"]
    assert removed.status_code == 204
    assert after.status_code == 200
    assert [item["id"] for item in after.json()["notes"]] == [first["id"]]
    assert missing.status_code == 404


def test_research_note_rejects_empty_title_and_extra_fields() -> None:
    app = create_app()
    session = _NoteSession(should_fail=True)

    def override():
        yield session

    app.dependency_overrides[get_db] = override
    with _client(app) as client:
        blank = client.post(
            "/api/v1/research/notes",
            json={"title": "   ", "body": "A note."},
        )
        extra = client.post(
            "/api/v1/research/notes",
            json={"title": "Desk check", "body": "A note.", "symbol": "BTC-USD"},
        )
        down = client.get("/api/v1/research/notes")

    assert blank.status_code == 422
    assert extra.status_code == 422
    assert down.status_code == 503
    assert down.json()["detail"] == "Research note store is unavailable."
    assert session.rows == []


class _EventSession:
    def __init__(self) -> None:
        self.rows: list[Any] = []

    def add(self, row: Any) -> None:
        if type(row).__name__ != "SourceEventRow":
            raise AssertionError(f"unexpected row {type(row).__name__}")
        self.rows.append(row)

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None

    def get(self, _model: object, key: object) -> Any | None:
        for row in self.rows:
            if row.id == key:
                return row
        return None

    def delete(self, row: Any) -> None:
        self.rows.remove(row)

    def scalars(self, _statement: object) -> list[Any]:
        return sorted(self.rows, key=lambda row: (row.recorded_at, str(row.id)), reverse=True)


def test_source_event_is_stored_without_sizing_or_a_position(monkeypatch) -> None:
    calls = {"size": 0}

    def counted_size(*_args: object, **_kwargs: object) -> None:
        calls["size"] += 1
        raise AssertionError("size calculator was called")

    monkeypatch.setattr("veytrix_risk.sizing.size_position", counted_size)
    app = create_app()
    session = _EventSession()

    def override():
        yield session

    app.dependency_overrides[get_db] = override
    payload = {
        "title": "Payrolls",
        "source": "Bureau of Labor Statistics release",
        "event_time": "2026-11-08T13:30:00Z",
        "first_public_at": "2026-11-08T13:30:05Z",
    }
    with _client(app) as client:
        created = client.post("/api/v1/research/source-events", json=payload)
        time.sleep(0.01)
        later = client.post(
            "/api/v1/research/source-events",
            json={
                **payload,
                "title": "Later note",
                "event_time": "2026-11-08T15:00:00Z",
                "first_public_at": "2026-11-08T15:00:01Z",
            },
        )
        listed = client.get("/api/v1/research/source-events")
        removed = client.delete(f"/api/v1/research/source-events/{later.json()['id']}")
        after = client.get("/api/v1/research/source-events")
        missing = client.delete(f"/api/v1/research/source-events/{later.json()['id']}")

    body = created.json()
    assert created.status_code == 200
    assert later.status_code == 200
    assert body["title"] == "Payrolls"
    assert body["source"] == "Bureau of Labor Statistics release"
    assert body["event_time"] == "2026-11-08T13:30:00Z"
    assert body["first_public_at"] == "2026-11-08T13:30:05Z"
    assert body["recorded_at"].endswith("Z")
    assert body["execution_permitted"] is False
    assert body["order_submitted"] is False
    assert "symbol" not in body
    assert "order_id" not in body
    assert listed.status_code == 200
    events = listed.json()["events"]
    assert [item["id"] for item in events] == [later.json()["id"], body["id"]]
    assert events[0]["recorded_at"] >= events[1]["recorded_at"]
    assert removed.status_code == 204
    assert after.status_code == 200
    assert [item["id"] for item in after.json()["events"]] == [body["id"]]
    assert missing.status_code == 404
    assert calls["size"] == 0
    assert [type(row).__name__ for row in session.rows] == ["SourceEventRow"]


def test_source_event_rejects_empty_source_extra_fields_and_naive_time() -> None:
    app = create_app()
    session = _EventSession()

    def override():
        yield session

    app.dependency_overrides[get_db] = override
    aware = {
        "title": "Payrolls",
        "source": "Bureau of Labor Statistics release",
        "event_time": "2026-11-08T13:30:00Z",
        "first_public_at": "2026-11-08T13:30:05Z",
    }
    with _client(app) as client:
        blank = client.post("/api/v1/research/source-events", json={**aware, "source": "   "})
        extra = client.post("/api/v1/research/source-events", json={**aware, "symbol": "BTC-USD"})
        naive = client.post(
            "/api/v1/research/source-events",
            json={**aware, "event_time": "2026-11-08T13:30:00"},
        )
        missing = client.post(
            "/api/v1/research/source-events",
            json={
                "title": "Payrolls",
                "source": "Bureau of Labor Statistics release",
                "event_time": "2026-11-08T13:30:00Z",
            },
        )

    assert blank.status_code == 422
    assert extra.status_code == 422
    assert naive.status_code == 422
    assert missing.status_code == 422
    assert session.rows == []
