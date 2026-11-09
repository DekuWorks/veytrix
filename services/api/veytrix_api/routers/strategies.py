"""MAC-01 read routes plus pause, resume, and kill switch. No route here submits an order.

The API process holds no broker credentials and constructs no broker client. Only the
`python -m veytrix_quant.mac01` runner can submit to the Alpaca Trading API, and live
submission needs the runner's live gate.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from veytrix_api.db import get_db
from veytrix_api.models import Mac01OrderRow, Mac01SignalRow, Mac01StateRow
from veytrix_api.schemas import (
    Mac01ChartMarker,
    Mac01ChartPoint,
    Mac01ChartResponse,
    Mac01OrderEntry,
    Mac01OrderListResponse,
    Mac01PerformanceResponse,
    Mac01ScheduleResponse,
    Mac01SignalEntry,
    Mac01SignalListResponse,
    Mac01StatusResponse,
)
from veytrix_quant.mac01 import DISCLAIMER
from veytrix_quant.mac01.config import Mac01Config, UnsafeConfiguration, load_config
from veytrix_quant.mac01.strategy import crossover_markers, rolling_sma

router = APIRouter(prefix="/strategies/mac-01", tags=["strategies"])
LEDGER_UNAVAILABLE = "MAC-01 ledger is unavailable."
SIGNAL_LIMIT = 100
ORDER_LIMIT = 100
DISPLAY = Decimal("0.0001")


def _timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    text = value.astimezone(UTC).isoformat()
    return f"{text[:-6]}Z" if text.endswith("+00:00") else text


def _money(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")


def _state(db: Session) -> Mac01StateRow:
    try:
        row = db.get(Mac01StateRow, 1)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=LEDGER_UNAVAILABLE) from exc
    if row is None:
        raise HTTPException(status_code=503, detail=LEDGER_UNAVAILABLE)
    return row


def _config() -> Mac01Config | None:
    try:
        return load_config()
    except UnsafeConfiguration:
        return None


def _mode(value: str | None) -> Literal["paper", "live"] | None:
    return value if value in ("paper", "live") else None  # type: ignore[return-value]


def _status(row: Mac01StateRow) -> Mac01StatusResponse:
    config = _config()
    money: Literal["paper", "real", "unknown"] = "unknown"
    if config is not None:
        money = "real" if config.mode == "live" else "paper"
    return Mac01StatusResponse(
        strategy="mac-01",
        strategy_version=config.strategy_version if config else None,
        symbol="AAPL",
        broker="alpaca_trading_api",
        order_route="none",
        order_submitter="cli_runner_only",
        config_valid=config is not None,
        config_mode=config.mode if config else None,
        money=money,
        config_live_enabled=config.live_enabled if config else None,
        config_expected_account_set=bool(config.expected_account_number) if config else None,
        config_submit_orders=config.submit_orders if config else None,
        config_kill_switch=config.kill_switch if config else None,
        max_notional_per_trade=_money(config.max_notional_per_trade) if config else None,
        max_position_notional=_money(config.max_position_notional) if config else None,
        max_orders_per_day=config.max_orders_per_day if config else None,
        last_mode=_mode(row.last_mode),
        paused=row.paused,
        kill_switch=row.kill_switch,
        last_run_at=_timestamp(row.last_run_at),
        last_run_status=row.last_run_status,
        last_run_message=row.last_run_message,
        last_session_date=row.last_session_date.isoformat() if row.last_session_date else None,
        disclaimer=DISCLAIMER,
    )


@router.get("/status", response_model=Mac01StatusResponse)
def status(db: Session = Depends(get_db)) -> Mac01StatusResponse:
    return _status(_state(db))


SCHEDULE_NOTE = (
    "The API does not start the scheduler and does not read the Alpaca calendar. "
    "A run still needs the CLI. Not investment advice."
)


@router.get("/schedule", response_model=Mac01ScheduleResponse)
def schedule_status() -> Mac01ScheduleResponse:
    """Published 09:35 New York clock. This route cannot start a run or pass --submit."""

    config = _config()
    return Mac01ScheduleResponse(
        strategy="mac-01",
        timezone="America/New_York",
        run_clock="09:35",
        delay_after_open_minutes=5,
        calendar="not_read",
        next_session="unknown",
        running=False,
        process="absent",
        submit_flag=False,
        can_start=False,
        config_valid=config is not None,
        config_mode=config.mode if config else None,
        config_submit_orders=config.submit_orders if config else None,
        config_live_enabled=config.live_enabled if config else None,
        alpaca_called=False,
        execution_permitted=False,
        order_submitted=False,
        order_route="absent",
        source="local_config",
        note=SCHEDULE_NOTE,
    )


def _set_flags(db: Session, **flags: bool) -> Mac01StatusResponse:
    row = _state(db)
    for name, value in flags.items():
        setattr(row, name, value)
    row.updated_at = datetime.now(UTC)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=LEDGER_UNAVAILABLE) from exc
    return _status(row)


@router.post("/pause", response_model=Mac01StatusResponse)
def pause(db: Session = Depends(get_db)) -> Mac01StatusResponse:
    return _set_flags(db, paused=True)


@router.post("/resume", response_model=Mac01StatusResponse)
def resume(db: Session = Depends(get_db)) -> Mac01StatusResponse:
    return _set_flags(db, paused=False)


@router.post("/kill-switch", response_model=Mac01StatusResponse)
def engage_kill_switch(db: Session = Depends(get_db)) -> Mac01StatusResponse:
    """Engage only. Releasing the kill switch needs the CLI on this machine."""

    return _set_flags(db, kill_switch=True)


@router.get("/signals", response_model=Mac01SignalListResponse)
def signals(db: Session = Depends(get_db)) -> Mac01SignalListResponse:
    try:
        rows = list(
            db.scalars(
                select(Mac01SignalRow)
                .order_by(Mac01SignalRow.session_date.desc())
                .limit(SIGNAL_LIMIT)
            )
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=LEDGER_UNAVAILABLE) from exc
    return Mac01SignalListResponse(
        signals=[
            Mac01SignalEntry(
                session_date=row.session_date.isoformat(),
                strategy_version=row.strategy_version,
                symbol=row.symbol,
                side=row.side,
                reason=row.reason,
                close=format(row.close, "f"),
                fast_prev=format(row.fast_prev, "f"),
                slow_prev=format(row.slow_prev, "f"),
                fast_cur=format(row.fast_cur, "f"),
                slow_cur=format(row.slow_cur, "f"),
                decision=row.decision,
                decision_reason=row.decision_reason,
                inputs_hash=row.inputs_hash,
                created_at=_timestamp(row.created_at) or "",
                decided_at=_timestamp(row.decided_at) or "",
            )
            for row in rows
        ]
    )


def _orders(db: Session, newest_first: bool = True) -> list[Mac01OrderRow]:
    order = Mac01OrderRow.created_at.desc() if newest_first else Mac01OrderRow.created_at.asc()
    try:
        return list(db.scalars(select(Mac01OrderRow).order_by(order)))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=LEDGER_UNAVAILABLE) from exc


@router.get("/orders", response_model=Mac01OrderListResponse)
def orders(db: Session = Depends(get_db)) -> Mac01OrderListResponse:
    rows = _orders(db)[:ORDER_LIMIT]
    return Mac01OrderListResponse(
        orders=[
            Mac01OrderEntry(
                client_order_id=row.client_order_id,
                mode=row.mode,
                session_date=row.session_date.isoformat(),
                side=row.side,
                notional=_money(row.notional),
                qty=_money(row.qty),
                order_type=row.order_type,
                time_in_force=row.time_in_force,
                status=row.status,
                broker_order_id=row.broker_order_id,
                filled_qty=format(row.filled_qty, "f"),
                filled_avg_price=_money(row.filled_avg_price),
                submitted_at=_timestamp(row.submitted_at),
                created_at=_timestamp(row.created_at) or "",
                updated_at=_timestamp(row.updated_at) or "",
                last_error=row.last_error,
            )
            for row in rows
        ]
    )


def realised_pl(rows: list[Mac01OrderRow]) -> tuple[Decimal | None, int]:
    """FIFO realised P&L from broker-reported fills only. Fees are not included."""

    lots: list[list[Decimal]] = []
    realised = Decimal(0)
    filled = 0
    for row in rows:
        if row.filled_qty <= 0 or row.filled_avg_price is None:
            continue
        filled += 1
        if row.side == "buy":
            lots.append([row.filled_qty, row.filled_avg_price])
            continue
        remaining = row.filled_qty
        while remaining > 0:
            if not lots:
                return None, filled
            lot = lots[0]
            take = min(lot[0], remaining)
            realised += (row.filled_avg_price - lot[1]) * take
            lot[0] -= take
            remaining -= take
            if lot[0] == 0:
                lots.pop(0)
    return realised, filled


@router.get("/performance", response_model=Mac01PerformanceResponse)
def performance(db: Session = Depends(get_db)) -> Mac01PerformanceResponse:
    state = _state(db)
    config = _config()
    mode = config.mode if config else (_mode(state.last_mode) or "paper")
    rows = [row for row in _orders(db, newest_first=False) if row.mode == mode]
    realised, filled = realised_pl(rows)
    has_position = (
        state.last_mode == mode
        and state.position_as_of is not None
        and state.position_unrealised_pl is not None
    )
    snapshot = state.position_as_of is not None and state.last_mode == mode
    return Mac01PerformanceResponse(
        mode=mode,
        realised_pl=_money(realised),
        realised_available=realised is not None,
        unrealised_pl=_money(state.position_unrealised_pl) if has_position else None,
        unrealised_available=has_position,
        position_qty=_money(state.position_qty) if snapshot else None,
        avg_entry_price=_money(state.position_avg_entry_price) if snapshot else None,
        market_price=_money(state.position_market_price) if snapshot else None,
        position_as_of=_timestamp(state.position_as_of) if snapshot else None,
        filled_orders=filled,
        note=(
            "Realised P&L uses broker-reported fills in the local ledger, FIFO, before fees. "
            "Unrealised P&L is the broker position snapshot from the last runner pass in this "
            f"mode. Mode {mode}: {'REAL money' if mode == 'live' else 'paper money'}. "
            "Not investment advice."
        ),
    )


def _chart_points(raw: object) -> tuple[list[str], list[Decimal]] | None:
    if not isinstance(raw, list):
        return None
    dates: list[str] = []
    closes: list[Decimal] = []
    for item in raw:
        if not isinstance(item, dict):
            return None
        day = item.get("session_date")
        close = item.get("close")
        if not isinstance(day, str) or not isinstance(close, str):
            return None
        try:
            value = Decimal(close)
        except InvalidOperation:
            return None
        if not value.is_finite() or value <= 0:
            return None
        dates.append(day)
        closes.append(value)
    return dates, closes


def _unavailable_chart(note: str) -> Mac01ChartResponse:
    return Mac01ChartResponse(
        available=False,
        symbol="AAPL",
        source=None,
        as_of=None,
        fast_period=None,
        slow_period=None,
        points=[],
        markers=[],
        note=note,
    )


@router.get("/chart", response_model=Mac01ChartResponse)
def chart(db: Session = Depends(get_db)) -> Mac01ChartResponse:
    snapshot = _state(db).chart
    if not isinstance(snapshot, dict):
        return _unavailable_chart("No runner pass has stored a chart yet. Nothing was invented.")
    fast = snapshot.get("fast_period")
    slow = snapshot.get("slow_period")
    parsed = _chart_points(snapshot.get("points"))
    if (
        parsed is None
        or not isinstance(fast, int)
        or not isinstance(slow, int)
        or not 0 < fast < slow
    ):
        return _unavailable_chart("Stored chart snapshot failed validation. Nothing was invented.")
    dates, closes = parsed
    fast_line = rolling_sma(closes, fast)
    slow_line = rolling_sma(closes, slow)
    markers = crossover_markers(dates, closes, fast, slow) if len(closes) > slow else []
    return Mac01ChartResponse(
        available=True,
        symbol="AAPL",
        source=str(snapshot.get("source") or "unknown"),
        as_of=str(snapshot.get("as_of") or "") or None,
        fast_period=fast,
        slow_period=slow,
        points=[
            Mac01ChartPoint(
                session_date=day,
                close=format(close, "f"),
                sma_fast=_money(f.quantize(DISPLAY)) if f is not None else None,
                sma_slow=_money(s.quantize(DISPLAY)) if s is not None else None,
            )
            for day, close, f, s in zip(dates, closes, fast_line, slow_line, strict=True)
        ],
        markers=[Mac01ChartMarker(session_date=day, side=side) for day, side in markers],
        note=(
            "Adjusted daily closes from the last MAC-01 runner pass. "
            "Alpaca market data. Not investment advice."
        ),
    )
