"""Paper desk cycles. One Coinbase product can be active. The rest stay honest.

A fill is written to the local ledger only. Broker execution stays false.
Unsupported asset classes are rows with no_provider. They are not registry desks.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from veytrix_api.models import DeskRunRow, PaperFillRow

Candle = tuple[datetime, Decimal]
Fetch = Callable[[], Sequence[Candle]]

FRESH = timedelta(days=2)
QUANTITY = Decimal("1")
SOURCE_COINBASE = "coinbase-exchange"
SOURCE_SAMPLE = "synthetic-sample"
SOURCE_NONE = "none"

BLOCKED = (
    ("STOCK-01", "idle", SOURCE_SAMPLE, "alpaca_market_data_absent"),
    ("ETF-01", "idle", SOURCE_SAMPLE, "alpaca_market_data_absent"),
    ("FUTURES-01", "blocked", SOURCE_NONE, "market_data_not_read"),
    ("DEFI-01", "blocked", SOURCE_NONE, "no_fresh_quote"),
    ("DAY-01", "idle", SOURCE_NONE, "not_a_market_feed"),
    ("SUPERVISOR-01", "idle", SOURCE_NONE, "not_a_market_feed"),
    ("RESEARCH-01", "idle", SOURCE_NONE, "not_a_market_feed"),
    ("RISK-01", "idle", SOURCE_NONE, "not_a_market_feed"),
    ("TREASURY-01", "idle", SOURCE_NONE, "not_a_market_feed"),
    ("YIELD", "blocked", SOURCE_NONE, "no_provider"),
    ("NFT", "blocked", SOURCE_NONE, "no_provider"),
    ("TAX-LIEN", "blocked", SOURCE_NONE, "no_provider"),
    ("LAND", "blocked", SOURCE_NONE, "no_provider"),
)


def _now() -> datetime:
    return datetime.now(UTC)


def _upsert(
    db: Session,
    code: str,
    state: str,
    moment: datetime,
    source_id: str,
    reason: str | None,
    worker_id: str,
    data_at: datetime | None = None,
    fill_id: uuid.UUID | None = None,
) -> None:
    row = db.get(DeskRunRow, code)
    if row is None:
        db.add(
            DeskRunRow(
                agent_code=code,
                state=state,
                heartbeat_at=moment,
                data_at=data_at,
                source_id=source_id,
                block_reason=reason,
                paper_fill_id=fill_id,
                worker_id=worker_id,
                updated_at=moment,
            )
        )
    else:
        row.state = state
        row.heartbeat_at = moment
        row.data_at = data_at
        row.source_id = source_id
        row.block_reason = reason
        row.paper_fill_id = fill_id or row.paper_fill_id
        row.worker_id = worker_id
        row.updated_at = moment
    db.flush()


def _fill(db: Session, bar_start: datetime, price: Decimal) -> uuid.UUID:
    existing = db.scalar(
        select(PaperFillRow).where(
            PaperFillRow.symbol == "BTC-USD",
            PaperFillRow.bar_start == bar_start,
        )
    )
    if existing is not None:
        return existing.id
    row = PaperFillRow(
        id=uuid.uuid4(),
        agent_code="CRYPTO-01",
        symbol="BTC-USD",
        price=price,
        quantity=QUANTITY,
        source_id=SOURCE_COINBASE,
        bar_start=bar_start,
        execution_permitted=False,
        order_submitted=False,
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        found = db.scalar(
            select(PaperFillRow).where(
                PaperFillRow.symbol == "BTC-USD",
                PaperFillRow.bar_start == bar_start,
            )
        )
        if found is None:
            raise
        return found.id
    return row.id


def _crypto(db: Session, fetch: Fetch, moment: datetime, worker_id: str) -> None:
    try:
        candles = list(fetch())
    except Exception:
        _upsert(
            db, "CRYPTO-01", "failed", moment, SOURCE_COINBASE, "coinbase_unavailable", worker_id
        )
        return
    if len(candles) < 2:
        _upsert(
            db, "CRYPTO-01", "failed", moment, SOURCE_COINBASE, "coinbase_unavailable", worker_id
        )
        return
    previous_start, previous_close = candles[-2]
    bar_start, close = candles[-1]
    del previous_start
    if close <= 0 or previous_close <= 0:
        _upsert(
            db, "CRYPTO-01", "failed", moment, SOURCE_COINBASE, "coinbase_unavailable", worker_id
        )
        return
    fresh = moment - bar_start <= FRESH and moment >= bar_start
    fill_id = None
    if fresh and close > previous_close:
        fill_id = _fill(db, bar_start, close)
    if fresh:
        _upsert(
            db,
            "CRYPTO-01",
            "active",
            moment,
            SOURCE_COINBASE,
            None,
            worker_id,
            data_at=bar_start,
            fill_id=fill_id,
        )
        return
    _upsert(
        db,
        "CRYPTO-01",
        "blocked",
        moment,
        SOURCE_COINBASE,
        "stale_candle",
        worker_id,
        data_at=bar_start,
    )


def cycle_desks(
    db: Session,
    *,
    fetch: Fetch,
    worker_id: str,
    now: datetime | None = None,
) -> None:
    """Write one heartbeat per desk. Only a fresh Coinbase rise can create a fill."""

    moment = now or _now()
    _crypto(db, fetch, moment, worker_id)
    for code, state, source_id, reason in BLOCKED:
        _upsert(db, code, state, moment, source_id, reason, worker_id)
    db.flush()
