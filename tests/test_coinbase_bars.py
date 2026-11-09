import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from urllib.error import URLError
from urllib.parse import parse_qs, urlparse

import pytest

from veytrix_market.coinbase import (
    DISCLAIMER,
    MINUTE_DISCLAIMER,
    PRODUCTS,
    QuoteUnavailable,
    clear_cache,
    daily_disclaimer,
    get_btc_usd_minute,
    get_daily,
    get_minute,
    get_ticker,
    minute_disclaimer,
    parse_coinbase_candles,
    parse_ticker,
    ticker_disclaimer,
)


def setup_function() -> None:
    clear_cache()


def test_parser_reads_coinbase_column_order_and_sorts_oldest_first() -> None:
    # Live column order on 7 November 2026: [time, low, high, open, close, volume].
    # The older row is only a fixture.
    payload = [
        [1794096000, "75545.34", "75830.11", "75753.95", "75767.33", "260.19458529"],
        [1794009600, "74000.00", "76000.00", "74500.10", "75000.00", "10.5"],
    ]

    bars = parse_coinbase_candles(payload, limit=2)

    assert bars[0].bar_start == datetime(2026, 11, 7, tzinfo=UTC)
    assert bars[1].bar_start == datetime(2026, 11, 8, tzinfo=UTC)
    assert bars[1].low == Decimal("75545.34")
    assert bars[1].close == Decimal("75767.33")
    assert bars[1].volume == Decimal("260.19458529")
    assert "not investment advice" in DISCLAIMER
    assert "No order is sent" in DISCLAIMER


def test_parser_rejects_floats_and_broken_ohlc() -> None:
    with pytest.raises(QuoteUnavailable):
        parse_coinbase_candles(
            [[1794096000, 75545.34, 75830.11, 75753.95, 75767.33, 10]],
            limit=1,
        )
    with pytest.raises(QuoteUnavailable):
        parse_coinbase_candles(
            [[1794096000, "10", "9", "8", "8.5", "1"]],
            limit=1,
        )


def test_ticker_parser_accepts_the_public_payload_and_rejects_floats() -> None:
    payload = {
        "ask": "75764.5",
        "bid": "75764.49",
        "volume": "2022.50285353",
        "trade_id": Decimal("1116967290"),
        "price": "75764.49",
        "size": "0.00000011",
        "time": "2026-11-08T03:55:44.792670175Z",
    }

    price, bid, ask, size, volume, trade_time, trade_id = parse_ticker(payload)

    assert price == Decimal("75764.49")
    assert bid == Decimal("75764.49")
    assert ask == Decimal("75764.5")
    assert size == Decimal("0.00000011")
    assert volume == Decimal("2022.50285353")
    assert trade_time.startswith("2026-11-08T03:55:44")
    assert trade_id == 1116967290
    with pytest.raises(QuoteUnavailable):
        parse_ticker({**payload, "price": 75764.49})


class _Body:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc: object) -> bool:
        return False


def test_minute_fetcher_uses_granularity_60_and_decimal_json() -> None:
    moment = datetime(2026, 11, 8, 3, 59, 8, tzinfo=UTC)
    bucket = int(moment.timestamp()) // 60 * 60
    seen: dict[str, str] = {}

    def opener(request, timeout: int) -> _Body:
        seen["url"] = request.full_url
        assert timeout == 10
        # A JSON number must be decoded with parse_float=Decimal, not left as float.
        payload = f'[[{bucket}, "75790.00", "75820.00", "75802.00", 75805.98, "2.5"]]'
        return _Body(payload.encode())

    series = get_btc_usd_minute(180, opener=opener, now=moment)

    parsed = urlparse(seen["url"])
    assert parsed.path == "/products/BTC-USD/candles"
    query = parse_qs(parsed.query)
    start = int(query["start"][0])
    end = int(query["end"][0])
    assert query["granularity"] == ["60"]
    assert end - start == 180 * 60
    assert (end - start) // 60 + 1 <= 300
    assert isinstance(series.bars[-1].close, Decimal)
    assert series.bars[-1].close == Decimal("75805.98")
    assert series.bars[-1].bar_start == datetime.fromtimestamp(bucket, tz=UTC)
    assert "Not a consolidated quote" in MINUTE_DISCLAIMER
    assert "No order is sent" in MINUTE_DISCLAIMER

    def cached(request, timeout: int) -> _Body:
        raise AssertionError(request.full_url)

    again = get_btc_usd_minute(180, opener=cached, now=moment.replace(second=20))
    assert again is series


def test_minute_window_stays_inside_the_coinbase_cap_and_fails_closed() -> None:
    moment = datetime(2026, 11, 8, 3, 59, 8, tzinfo=UTC)
    seen: dict[str, str] = {}

    def opener(request, timeout: int) -> _Body:
        seen["url"] = request.full_url
        assert timeout == 10
        bucket = int(moment.timestamp()) // 60 * 60
        row = [bucket, "100.00", "110.00", "101.00", "105.00", "1"]
        return _Body(json.dumps([row]).encode())

    get_btc_usd_minute(300, opener=opener, now=moment)
    query = parse_qs(urlparse(seen["url"]).query)
    start = int(query["start"][0])
    end = int(query["end"][0])
    assert end - start <= 299 * 60
    assert (end - start) // 60 + 1 <= 300

    def down(request, timeout: int) -> _Body:
        raise URLError("down")

    with pytest.raises(QuoteUnavailable):
        get_btc_usd_minute(30, opener=down, now=moment)


def test_eth_shares_the_parser_and_does_not_call_the_btc_url() -> None:
    moment = datetime(2026, 11, 8, 4, 12, tzinfo=UTC)
    bucket = int(moment.timestamp()) // 60 * 60
    seen: list[str] = []

    def opener(request, timeout: int) -> _Body:
        seen.append(request.full_url)
        assert timeout == 10
        path = urlparse(request.full_url).path
        if path.endswith("/ticker"):
            payload = {
                "ask": "3210.60",
                "bid": "3210.50",
                "volume": "12345.6",
                "trade_id": 88001122,
                "price": "3210.55",
                "size": "0.42",
                "time": "2026-11-08T04:11:59.100000Z",
            }
            return _Body(json.dumps(payload).encode())
        row = [bucket, "3206.00", "3212.00", "3208.00", "3210.55", "12.5"]
        return _Body(json.dumps([row]).encode())

    minute = get_minute("ETH-USD", 180, opener=opener, now=moment)
    daily = get_daily("ETH-USD", 2, opener=opener, now=moment)
    ticker = get_ticker("ETH-USD", opener=opener, now=moment)

    assert [urlparse(url).path for url in seen] == [
        "/products/ETH-USD/candles",
        "/products/ETH-USD/candles",
        "/products/ETH-USD/ticker",
    ]
    queries = [parse_qs(urlparse(url).query) for url in seen]
    assert queries[0]["granularity"] == ["60"]
    assert int(queries[0]["end"][0]) - int(queries[0]["start"][0]) == 180 * 60
    assert queries[1]["granularity"] == ["86400"]
    assert queries[2] == {}
    assert all("BTC-USD" not in url for url in seen)
    assert minute.bars[-1].close == Decimal("3210.55")
    assert daily.bars[-1].close == Decimal("3210.55")
    assert ticker.price == Decimal("3210.55")
    assert "ETH-USD" in minute_disclaimer("ETH-USD")
    assert "BTC-USD" not in minute_disclaimer("ETH-USD")
    assert "Not a consolidated quote" in daily_disclaimer("ETH-USD")
    assert "No order is sent" in ticker_disclaimer("ETH-USD")
    assert "not investment advice" in ticker_disclaimer("ETH-USD")

    def cached(request, timeout: int) -> _Body:
        raise AssertionError(request.full_url)

    assert get_minute("ETH-USD", 180, opener=cached, now=moment.replace(second=10)) is minute
    assert get_ticker("ETH-USD", opener=cached, now=moment) is ticker


def test_sol_uses_the_shared_parser_and_a_failure_does_not_return_the_fixture() -> None:
    moment = datetime(2026, 11, 8, 5, 20, tzinfo=UTC)
    bucket = int(moment.timestamp()) // 60 * 60
    seen: list[str] = []

    def opener(request, timeout: int) -> _Body:
        seen.append(request.full_url)
        assert timeout == 10
        path = urlparse(request.full_url).path
        if path.endswith("/ticker"):
            payload = {
                "ask": "186.41",
                "bid": "186.39",
                "volume": "88000.1",
                "trade_id": 99001122,
                "price": "186.40",
                "size": "3.2",
                "time": "2026-11-08T05:19:40.000000Z",
            }
            return _Body(json.dumps(payload).encode())
        row = [bucket, "185.90", "186.80", "186.10", "186.42", "40.5"]
        return _Body(json.dumps([row]).encode())

    minute = get_minute("SOL-USD", 180, opener=opener, now=moment)
    daily = get_daily("SOL-USD", 14, opener=opener, now=moment)
    ticker = get_ticker("SOL-USD", opener=opener, now=moment)

    assert list(PRODUCTS) == ["BTC-USD", "ETH-USD", "SOL-USD"]
    assert [urlparse(url).path for url in seen] == [
        "/products/SOL-USD/candles",
        "/products/SOL-USD/candles",
        "/products/SOL-USD/ticker",
    ]
    queries = [parse_qs(urlparse(url).query) for url in seen]
    assert queries[0]["granularity"] == ["60"]
    assert int(queries[0]["end"][0]) - int(queries[0]["start"][0]) == 180 * 60
    assert queries[1]["granularity"] == ["86400"]
    assert all("BTC-USD" not in url and "ETH-USD" not in url for url in seen)
    assert minute.bars[-1].close == Decimal("186.42")
    assert daily.bars[-1].close == Decimal("186.42")
    assert ticker.price == Decimal("186.40")
    assert "SOL-USD" in minute_disclaimer("SOL-USD")
    assert "Not a consolidated quote" in daily_disclaimer("SOL-USD")
    assert "No order is sent" in ticker_disclaimer("SOL-USD")

    def down(request, timeout: int) -> _Body:
        raise URLError("down")

    later = moment + timedelta(seconds=2)
    with pytest.raises(QuoteUnavailable) as caught:
        get_ticker("SOL-USD", opener=down, now=later)
    assert "186.40" not in str(caught.value)
    assert "186.42" not in str(caught.value)


def test_unknown_product_and_upstream_failure_do_not_invent_a_price() -> None:
    moment = datetime(2026, 11, 8, 4, 12, tzinfo=UTC)

    def opener(request, timeout: int) -> _Body:
        assert timeout == 10
        path = urlparse(request.full_url).path
        if path == "/products/BTC-USD/ticker":
            payload = {
                "ask": "75764.50",
                "bid": "75764.49",
                "volume": "10",
                "trade_id": 7,
                "price": "75764.49",
                "size": "0.01",
                "time": "2026-11-08T04:12:00.000000Z",
            }
            return _Body(json.dumps(payload).encode())
        raise URLError("down")

    btc = get_ticker("BTC-USD", opener=opener, now=moment)
    assert btc.price == Decimal("75764.49")
    with pytest.raises(QuoteUnavailable) as caught:
        get_ticker("ETH-USD", opener=opener, now=moment)
    assert "75764.49" not in str(caught.value)
    assert "3210.55" not in str(caught.value)

    def refused(request, timeout: int) -> _Body:
        raise AssertionError(request.full_url)

    for product_id in (
        "DOGE-USD",
        "ETH-USD/../BTC-USD",
        "https://evil.test/products/ETH-USD",
        "btc-usd",
    ):
        with pytest.raises(QuoteUnavailable):
            get_minute(product_id, 30, opener=refused, now=moment)
        with pytest.raises(QuoteUnavailable):
            get_daily(product_id, 2, opener=refused, now=moment)
        with pytest.raises(QuoteUnavailable):
            get_ticker(product_id, opener=refused, now=moment)
