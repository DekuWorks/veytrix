"""Alpaca market data for MAC-01: adjusted daily AAPL bars via alpaca-py.

StockHistoricalDataClient with TimeFrame.Day, Adjustment.ALL (split, dividend, and spin-off
adjusted), and the IEX feed unless config says SIP. alpaca-py parses prices as floats; each one
is converted through its shortest repr into Decimal before any arithmetic.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, Literal

from alpaca.data.enums import Adjustment, DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from veytrix_quant.mac01.alpaca_trading import BrokerError, call_broker, harden_client
from veytrix_quant.mac01.data import NEW_YORK, DailyBar, DataUnavailable

FEEDS = {"iex": DataFeed.IEX, "sip": DataFeed.SIP}


def _price(value: Any, field: str) -> Decimal:
    if value is None or isinstance(value, bool) or not isinstance(value, int | float | Decimal):
        raise DataUnavailable(f"Bar {field} is missing or not a number.")
    number = Decimal(repr(value)) if isinstance(value, float) else Decimal(value)
    if not number.is_finite():
        raise DataUnavailable(f"Bar {field} is not finite.")
    return number


def to_bar(bar: Any) -> DailyBar:
    stamp = getattr(bar, "timestamp", None)
    if not isinstance(stamp, datetime) or stamp.tzinfo is None:
        raise DataUnavailable("Bar timestamp is missing or has no timezone.")
    return DailyBar(
        session_date=stamp.astimezone(NEW_YORK).date(),
        open=_price(bar.open, "open"),
        high=_price(bar.high, "high"),
        low=_price(bar.low, "low"),
        close=_price(bar.close, "close"),
        volume=_price(bar.volume if bar.volume is not None else 0, "volume"),
    )


class AlpacaMarketData:
    """Adjusted daily bars from Alpaca market data. Read-only."""

    def __init__(
        self,
        api_key: str,
        secret_key: str,
        *,
        feed: Literal["iex", "sip"] = "iex",
        client: Any | None = None,
    ) -> None:
        if feed not in FEEDS:
            raise ValueError("feed must be iex or sip.")
        if client is None:
            if not api_key or not secret_key:
                raise ValueError("Alpaca credentials are required for market data.")
            client = StockHistoricalDataClient(api_key, secret_key)
            harden_client(client)
        self.feed = feed
        self.source = f"alpaca-{feed}-adjusted"
        self._client = client

    def __repr__(self) -> str:
        return f"AlpacaMarketData(feed={self.feed!r})"

    def daily_bars(self, symbol: str, start: date, end: date) -> list[DailyBar]:
        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Day,
            start=datetime.combine(start, time.min, tzinfo=NEW_YORK),
            end=datetime.combine(end + timedelta(days=1), time.min, tzinfo=NEW_YORK),
            adjustment=Adjustment.ALL,
            feed=FEEDS[self.feed],
        )
        try:
            barset = call_broker(lambda: self._client.get_stock_bars(request), "daily bars")
        except BrokerError as exc:
            raise DataUnavailable(f"Market data unavailable: {exc}") from exc
        data = getattr(barset, "data", None)
        if not isinstance(data, dict):
            raise DataUnavailable("Market data response has no bar set.")
        return [to_bar(item) for item in data.get(symbol, [])]
