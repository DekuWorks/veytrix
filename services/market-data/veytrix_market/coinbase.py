"""Coinbase Exchange public candles for an explicit product list.

BTC-USD, ETH-USD, and SOL-USD share one parser. Daily bars and a short
1-minute window are fetched for personal display. The series is not stored
in git, not written to the database, and not a substitute when the request fails.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SOURCE_ID = "coinbase-exchange"
PRODUCT_ID = "BTC-USD"
ProductId = Literal["BTC-USD", "ETH-USD", "SOL-USD"]
PRODUCTS: dict[ProductId, str] = {
    "BTC-USD": "Bitcoin / US dollar",
    "ETH-USD": "Ether / US dollar",
    "SOL-USD": "Solana / US dollar",
}
EXCHANGE_ORIGIN = "https://api.exchange.coinbase.com"
USER_AGENT = "Veytrix personal research (local display; not redistributed)"
CALENDAR_NOTE = "Coinbase daily buckets start at 00:00 UTC. This is not an equity session calendar."
MINUTE_CALENDAR_NOTE = (
    "Each bar is one Coinbase minute, starting on the minute in UTC. "
    "This is not a consolidated quote."
)
PRICE_TICK = Decimal("0.01")
VOLUME_TICK = Decimal("0.00000001")
CACHE_TTL = timedelta(minutes=15)
MINUTE_TTL = timedelta(seconds=30)
TICKER_TTL = timedelta(seconds=1)
MINUTE_GRANULARITY = 60
# Coinbase rejects a candle request that can exceed 300 buckets. An unaligned
# window of N minutes can touch N+1 buckets, so the query span stops at 299.
MAX_MINUTE_SPAN = 299


class QuoteUnavailable(Exception):
    """The upstream candle request could not be turned into a series."""


def require_product(product_id: str) -> str:
    """Return a product id only when it is on the personal display list."""

    if product_id not in PRODUCTS:
        raise QuoteUnavailable("That product is not on the Coinbase display list.")
    return product_id


def candles_url(product_id: str) -> str:
    product = require_product(product_id)
    return f"{EXCHANGE_ORIGIN}/products/{product}/candles"


def ticker_url(product_id: str) -> str:
    product = require_product(product_id)
    return f"{EXCHANGE_ORIGIN}/products/{product}/ticker"


CANDLES_URL = candles_url(PRODUCT_ID)
TICKER_URL = ticker_url(PRODUCT_ID)


def daily_disclaimer(product_id: str) -> str:
    product = require_product(product_id)
    return (
        f"{product} daily candles from the Coinbase Exchange public market-data API. "
        "Personal research display on this machine only. Not a consolidated quote, "
        "not redistributed, and not investment advice. No order is sent."
    )


def ticker_disclaimer(product_id: str) -> str:
    product = require_product(product_id)
    return (
        f"Live {product} last trade from the Coinbase Exchange public ticker. "
        "Personal display on this machine only. Not a consolidated quote, "
        "not redistributed, and not investment advice. No order is sent."
    )


def minute_disclaimer(product_id: str) -> str:
    product = require_product(product_id)
    return (
        f"{product} 1-minute candles from the Coinbase Exchange public market-data API. "
        "Personal display on this machine only. Not a consolidated quote, "
        "not redistributed, and not investment advice. No order is sent."
    )


DISCLAIMER = daily_disclaimer(PRODUCT_ID)
TICKER_DISCLAIMER = ticker_disclaimer(PRODUCT_ID)
MINUTE_DISCLAIMER = minute_disclaimer(PRODUCT_ID)
_cache: dict[tuple[str, int], tuple[datetime, QuoteSeries]] = {}
_minute_cache: dict[tuple[str, int], tuple[datetime, QuoteSeries]] = {}
_ticker_cache: dict[str, tuple[datetime, LiveTicker]] = {}


@dataclass(frozen=True)
class DailyBar:
    bar_start: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal

    def __post_init__(self) -> None:
        if self.bar_start.tzinfo is None or self.bar_start.utcoffset() != timedelta(0):
            raise ValueError("bar_start must be an aware UTC timestamp.")
        for name in ("open", "high", "low", "close", "volume"):
            value = getattr(self, name)
            if isinstance(value, float) or not isinstance(value, Decimal):
                raise ValueError(f"{name} must be Decimal.")
            if value <= 0:
                raise ValueError(f"{name} must be positive.")
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close):
            raise ValueError("OHLC invariant failed.")


@dataclass(frozen=True)
class QuoteSeries:
    bars: tuple[DailyBar, ...]
    retrieved_at: datetime

    @property
    def last(self) -> DailyBar:
        return self.bars[-1]

    @property
    def previous_close(self) -> Decimal | None:
        if len(self.bars) < 2:
            return None
        return self.bars[-2].close

    @property
    def change(self) -> Decimal | None:
        previous = self.previous_close
        if previous is None:
            return None
        return self.last.close - previous

    @property
    def change_percent(self) -> Decimal | None:
        previous = self.previous_close
        change = self.change
        if previous is None or change is None or previous == 0:
            return None
        return (change / previous) * Decimal(100)


def money(value: Decimal) -> str:
    return format(value.quantize(PRICE_TICK, rounding=ROUND_HALF_UP), "f")


def signed_money(value: Decimal) -> str:
    text = money(value)
    if value > 0:
        return f"+{text}"
    return text


def signed_percent(value: Decimal) -> str:
    text = money(value)
    if value > 0:
        return f"+{text}"
    return text


def volume_text(value: Decimal) -> str:
    text = format(value.quantize(VOLUME_TICK, rounding=ROUND_HALF_UP), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool) or isinstance(value, float) or not isinstance(value, (int, str)):
        raise QuoteUnavailable("Candle values must be decoded as Decimal, not binary floats.")
    try:
        return Decimal(value)
    except Exception as exc:
        raise QuoteUnavailable("A candle value was not a decimal.") from exc


def _timestamp(value: object) -> datetime:
    if isinstance(value, Decimal):
        if value != value.to_integral_value():
            raise QuoteUnavailable("Candle time must be whole seconds.")
        seconds = int(value)
    elif isinstance(value, int) and not isinstance(value, bool):
        seconds = value
    else:
        raise QuoteUnavailable("Candle time must be whole seconds.")
    return datetime.fromtimestamp(seconds, tz=UTC)


def parse_coinbase_candles(payload: object, *, limit: int) -> tuple[DailyBar, ...]:
    """Parse `[time, low, high, open, close, volume]` rows, oldest first."""

    if limit < 1 or limit > 300:
        raise QuoteUnavailable("limit must be between 1 and 300.")
    if not isinstance(payload, list) or not payload:
        raise QuoteUnavailable("Coinbase returned no candles.")
    bars: list[DailyBar] = []
    seen: set[datetime] = set()
    for row in payload:
        if not isinstance(row, list) or len(row) < 6:
            raise QuoteUnavailable("A candle row was incomplete.")
        start = _timestamp(row[0])
        if start in seen:
            raise QuoteUnavailable("Coinbase returned a duplicate candle.")
        seen.add(start)
        try:
            bars.append(
                DailyBar(
                    bar_start=start,
                    low=_decimal(row[1]),
                    high=_decimal(row[2]),
                    open=_decimal(row[3]),
                    close=_decimal(row[4]),
                    volume=_decimal(row[5]),
                )
            )
        except ValueError as exc:
            raise QuoteUnavailable("A candle failed the OHLC checks.") from exc
    bars.sort(key=lambda bar: bar.bar_start)
    return tuple(bars[-limit:])


def _load_payload(url: str, opener) -> object:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    try:
        with opener(request, timeout=10) as response:
            body = response.read()
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise QuoteUnavailable("Coinbase did not return candles.") from exc
    try:
        return json.loads(body.decode("utf-8"), parse_float=Decimal, parse_int=Decimal)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise QuoteUnavailable("Coinbase returned data that was not JSON.") from exc


def _fresh(cached: tuple[datetime, object] | None, moment: datetime, ttl: timedelta) -> bool:
    return cached is not None and moment - cached[0] < ttl and moment >= cached[0]


def get_daily(
    product_id: str,
    limit: int = 120,
    *,
    opener=urlopen,
    now: datetime | None = None,
) -> QuoteSeries:
    product = require_product(product_id)
    if limit < 1 or limit > 300:
        raise QuoteUnavailable("limit must be between 1 and 300.")
    moment = now or datetime.now(UTC)
    cached = _cache.get((product, limit))
    if _fresh(cached, moment, CACHE_TTL):
        assert cached is not None
        return cached[1]
    start = moment - timedelta(days=limit + 3)
    query = urlencode(
        {
            "granularity": 86400,
            "start": int(start.timestamp()),
            "end": int(moment.timestamp()),
        }
    )
    payload = _load_payload(f"{candles_url(product)}?{query}", opener)
    series = QuoteSeries(
        bars=parse_coinbase_candles(payload, limit=limit),
        retrieved_at=moment,
    )
    _cache[(product, limit)] = (moment, series)
    return series


def _minute_window(moment: datetime, limit: int) -> tuple[int, int]:
    end = int(moment.timestamp())
    span = min(limit, MAX_MINUTE_SPAN)
    return end - (span * MINUTE_GRANULARITY), end


def get_minute(
    product_id: str,
    limit: int = 180,
    *,
    opener=urlopen,
    now: datetime | None = None,
) -> QuoteSeries:
    """Last few hours of 1-minute candles. Granularity is 60 seconds."""

    product = require_product(product_id)
    if limit < 1 or limit > 300:
        raise QuoteUnavailable("limit must be between 1 and 300.")
    moment = now or datetime.now(UTC)
    cached = _minute_cache.get((product, limit))
    if _fresh(cached, moment, MINUTE_TTL):
        assert cached is not None
        return cached[1]
    start, end = _minute_window(moment, limit)
    query = urlencode({"granularity": MINUTE_GRANULARITY, "start": start, "end": end})
    payload = _load_payload(f"{candles_url(product)}?{query}", opener)
    series = QuoteSeries(
        bars=parse_coinbase_candles(payload, limit=limit),
        retrieved_at=moment,
    )
    _minute_cache[(product, limit)] = (moment, series)
    return series


@dataclass(frozen=True)
class LiveTicker:
    price: Decimal
    bid: Decimal
    ask: Decimal
    size: Decimal
    volume: Decimal
    trade_time: str
    trade_id: int
    retrieved_at: datetime

    def __post_init__(self) -> None:
        for name in ("price", "bid", "ask", "size", "volume"):
            value = getattr(self, name)
            if isinstance(value, float) or not isinstance(value, Decimal) or value < 0:
                raise ValueError(f"{name} must be a non-negative Decimal.")
        if self.price <= 0 or self.bid <= 0 or self.ask <= 0:
            raise ValueError("price, bid, and ask must be positive.")
        if "T" not in self.trade_time:
            raise ValueError("trade_time must be an exchange timestamp.")


def parse_ticker(payload: object) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal, str, int]:
    if not isinstance(payload, dict):
        raise QuoteUnavailable("Coinbase ticker was not an object.")
    try:
        price = _decimal(payload["price"])
        bid = _decimal(payload["bid"])
        ask = _decimal(payload["ask"])
        size = _decimal(payload["size"])
        volume = _decimal(payload["volume"])
    except KeyError as exc:
        raise QuoteUnavailable("Coinbase ticker was missing a field.") from exc
    except QuoteUnavailable:
        raise
    trade_time = payload.get("time")
    trade_id = payload.get("trade_id")
    if not isinstance(trade_time, str) or "T" not in trade_time:
        raise QuoteUnavailable("Coinbase ticker had no trade time.")
    if isinstance(trade_id, Decimal):
        if trade_id != trade_id.to_integral_value():
            raise QuoteUnavailable("Trade id must be a whole number.")
        trade_id = int(trade_id)
    if isinstance(trade_id, bool) or not isinstance(trade_id, int):
        raise QuoteUnavailable("Trade id must be a whole number.")
    try:
        LiveTicker(
            price=price,
            bid=bid,
            ask=ask,
            size=size,
            volume=volume,
            trade_time=trade_time,
            trade_id=trade_id,
            retrieved_at=datetime.now(UTC),
        )
    except ValueError as exc:
        raise QuoteUnavailable("Coinbase ticker failed validation.") from exc
    return price, bid, ask, size, volume, trade_time, trade_id


def get_ticker(
    product_id: str,
    *,
    opener=urlopen,
    now: datetime | None = None,
) -> LiveTicker:
    product = require_product(product_id)
    moment = now or datetime.now(UTC)
    cached = _ticker_cache.get(product)
    if _fresh(cached, moment, TICKER_TTL):
        assert cached is not None
        return cached[1]
    payload = _load_payload(ticker_url(product), opener)
    price, bid, ask, size, volume, trade_time, trade_id = parse_ticker(payload)
    ticker = LiveTicker(
        price=price,
        bid=bid,
        ask=ask,
        size=size,
        volume=volume,
        trade_time=trade_time,
        trade_id=trade_id,
        retrieved_at=moment,
    )
    _ticker_cache[product] = (moment, ticker)
    return ticker


def get_btc_usd_daily(
    limit: int = 120,
    *,
    opener=urlopen,
    now: datetime | None = None,
) -> QuoteSeries:
    return get_daily(PRODUCT_ID, limit, opener=opener, now=now)


def get_btc_usd_minute(
    limit: int = 180,
    *,
    opener=urlopen,
    now: datetime | None = None,
) -> QuoteSeries:
    return get_minute(PRODUCT_ID, limit, opener=opener, now=now)


def get_btc_usd_ticker(*, opener=urlopen, now: datetime | None = None) -> LiveTicker:
    return get_ticker(PRODUCT_ID, opener=opener, now=now)


def clear_cache() -> None:
    _cache.clear()
    _minute_cache.clear()
    _ticker_cache.clear()
