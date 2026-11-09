"""SAMPLE stays synthetic. Listed Coinbase products are fetched live and never replaced."""

from __future__ import annotations

from datetime import UTC
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from veytrix_api.schemas import (
    BarResponse,
    BarsResponse,
    InstrumentListResponse,
    InstrumentResponse,
    TickerResponse,
)
from veytrix_market.coinbase import (
    CALENDAR_NOTE,
    MINUTE_CALENDAR_NOTE,
    PRODUCTS,
    SOURCE_ID,
    QuoteSeries,
    QuoteUnavailable,
    candles_url,
    daily_disclaimer,
    get_daily,
    get_minute,
    get_ticker,
    minute_disclaimer,
    money,
    signed_money,
    signed_percent,
    ticker_disclaimer,
    volume_text,
)
from veytrix_market.sample import SAMPLE_DISCLAIMER, SEED, generate_sample_bars, sample_instrument

router = APIRouter(prefix="/market", tags=["market"])
SAMPLE_CALENDAR_NOTE = "Weekend sessions are omitted. Exchange holidays are not modelled."
LIST_DISCLAIMER = (
    "SAMPLE is synthetic. BTC-USD, ETH-USD, and SOL-USD are live Coinbase Exchange tickers, "
    "1-minute candles, and daily candles for personal research on this machine. "
    "None of these figures is a consolidated quote or investment advice. No order is sent."
)


def _text(value: Decimal) -> str:
    return format(value, "f")


def _stamp(value) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sample_instrument() -> InstrumentResponse:
    instrument = sample_instrument()
    return InstrumentResponse(
        symbol="SAMPLE",
        venue="SIM",
        asset_type="equity",
        currency="USD",
        source_id="synthetic-sample",
        name=instrument.name,
        timezone=instrument.timezone,
        calendar=instrument.calendar,
        calendar_note=SAMPLE_CALENDAR_NOTE,
        tick_size=_text(instrument.tick_size),
        contract_multiplier=_text(instrument.contract_multiplier),
        synthetic=True,
    )


def _coinbase_instrument(product_id: str) -> InstrumentResponse:
    return InstrumentResponse(
        symbol=product_id,
        venue="COINBASE",
        asset_type="crypto",
        currency="USD",
        source_id=SOURCE_ID,
        name=PRODUCTS[product_id],
        timezone="UTC",
        calendar="24/7",
        calendar_note=CALENDAR_NOTE,
        tick_size="0.01",
        contract_multiplier="1",
        synthetic=False,
    )


def _sample_bars(limit: int) -> BarsResponse:
    bars = generate_sample_bars(count=limit)
    last = bars[-1]
    previous = bars[-2].close if len(bars) > 1 else None
    change = last.close - previous if previous is not None else None
    change_percent = (change / previous) * Decimal(100) if change is not None and previous else None
    return BarsResponse(
        symbol="SAMPLE",
        venue="SIM",
        asset_type="equity",
        currency="USD",
        source_id="synthetic-sample",
        interval="1d",
        seed=SEED,
        synthetic=True,
        calendar_note=SAMPLE_CALENDAR_NOTE,
        disclaimer=SAMPLE_DISCLAIMER,
        last_close=_text(last.close),
        previous_close=_text(previous) if previous is not None else None,
        change=signed_money(change) if change is not None else None,
        change_percent=signed_percent(change_percent) if change_percent is not None else None,
        retrieved_at=None,
        source_url=None,
        bars=[
            BarResponse(
                bar_start=_stamp(bar.bar_start),
                open=_text(bar.open),
                high=_text(bar.high),
                low=_text(bar.low),
                close=_text(bar.close),
                volume=str(bar.volume),
            )
            for bar in bars
        ],
    )


def _series_bars(
    series: QuoteSeries,
    *,
    product_id: str,
    interval: Literal["1d", "1m"],
    calendar_note: str,
    disclaimer: str,
) -> BarsResponse:
    change = series.change
    change_percent = series.change_percent
    return BarsResponse(
        symbol=product_id,
        venue="COINBASE",
        asset_type="crypto",
        currency="USD",
        source_id=SOURCE_ID,
        interval=interval,
        seed=None,
        synthetic=False,
        calendar_note=calendar_note,
        disclaimer=disclaimer,
        last_close=money(series.last.close),
        previous_close=money(series.previous_close) if series.previous_close is not None else None,
        change=signed_money(change) if change is not None else None,
        change_percent=signed_percent(change_percent) if change_percent is not None else None,
        retrieved_at=_stamp(series.retrieved_at),
        source_url=candles_url(product_id),
        bars=[
            BarResponse(
                bar_start=_stamp(bar.bar_start),
                open=money(bar.open),
                high=money(bar.high),
                low=money(bar.low),
                close=money(bar.close),
                volume=volume_text(bar.volume),
            )
            for bar in series.bars
        ],
    )


def _coinbase_bars(product_id: str, limit: int, interval: Literal["1d", "1m"]) -> BarsResponse:
    if interval == "1m":
        try:
            series = get_minute(product_id, limit)
        except QuoteUnavailable as exc:
            raise HTTPException(
                status_code=502,
                detail=(
                    f"Coinbase 1-minute candles for {product_id} are unavailable. "
                    "No substitute prices were generated."
                ),
            ) from exc
        return _series_bars(
            series,
            product_id=product_id,
            interval="1m",
            calendar_note=MINUTE_CALENDAR_NOTE,
            disclaimer=minute_disclaimer(product_id),
        )
    try:
        series = get_daily(product_id, limit)
    except QuoteUnavailable as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                f"Coinbase daily candles for {product_id} are unavailable. "
                "No substitute prices were generated."
            ),
        ) from exc
    return _series_bars(
        series,
        product_id=product_id,
        interval="1d",
        calendar_note=CALENDAR_NOTE,
        disclaimer=daily_disclaimer(product_id),
    )


@router.get("/instruments", response_model=InstrumentListResponse)
def list_instruments() -> InstrumentListResponse:
    return InstrumentListResponse(
        instruments=[
            *(_coinbase_instrument(product_id) for product_id in PRODUCTS),
            _sample_instrument(),
        ],
        disclaimer=LIST_DISCLAIMER,
    )


@router.get("/instruments/{symbol}/ticker", response_model=TickerResponse)
def instrument_ticker(symbol: str) -> TickerResponse:
    if symbol not in PRODUCTS:
        raise HTTPException(
            status_code=404,
            detail="A live ticker is available for BTC-USD, ETH-USD, and SOL-USD only.",
        )
    try:
        ticker = get_ticker(symbol)
    except QuoteUnavailable as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                f"Coinbase ticker for {symbol} is unavailable. No substitute price was generated."
            ),
        ) from exc
    return TickerResponse(
        symbol=symbol,
        venue="COINBASE",
        source_id=SOURCE_ID,
        synthetic=False,
        price=money(ticker.price),
        bid=money(ticker.bid),
        ask=money(ticker.ask),
        size=volume_text(ticker.size),
        volume=volume_text(ticker.volume),
        trade_time=ticker.trade_time,
        trade_id=ticker.trade_id,
        retrieved_at=_stamp(ticker.retrieved_at),
        disclaimer=ticker_disclaimer(symbol),
    )


@router.get("/instruments/{symbol}/bars", response_model=BarsResponse)
def instrument_bars(
    symbol: str,
    limit: int = Query(default=120, ge=1, le=300),
    interval: Literal["1d", "1m"] = Query(default="1d"),
) -> BarsResponse:
    if symbol == "SAMPLE":
        if interval != "1d":
            raise HTTPException(status_code=422, detail="SAMPLE only has the synthetic 1d series.")
        if limit > 252:
            raise HTTPException(status_code=422, detail="SAMPLE supports at most 252 bars.")
        return _sample_bars(limit)
    if symbol in PRODUCTS:
        return _coinbase_bars(symbol, limit, interval)
    raise HTTPException(
        status_code=404,
        detail="Unknown instrument. Available symbols are BTC-USD, ETH-USD, SOL-USD, and SAMPLE.",
    )
