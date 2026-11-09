"""Postgres ledger for MAC-01 signals, Trading API orders, and the control row."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from veytrix_api.models import Mac01OrderRow, Mac01SignalRow, Mac01StateRow
from veytrix_quant.mac01.data import NEW_YORK

if TYPE_CHECKING:
    from veytrix_quant.mac01.alpaca_trading import BrokerOrder, PositionSnapshot

ADVISORY_LOCK_KEY = 0x6D61633031  # "mac01"
STATE_ID = 1
TERMINAL_STATUSES = frozenset(
    {"filled", "canceled", "expired", "rejected", "replaced", "not_found"}
)


def _now() -> datetime:
    return datetime.now(UTC)


class Ledger:
    def __init__(self, engine: Engine, clock: Callable[[], datetime] = _now) -> None:
        self.engine = engine
        self.sessions = sessionmaker(engine, expire_on_commit=False)
        self.clock = clock

    def _state(self, session: Session) -> Mac01StateRow:
        row = session.get(Mac01StateRow, STATE_ID)
        if row is None:
            row = Mac01StateRow(
                id=STATE_ID, paused=False, kill_switch=False, updated_at=self.clock()
            )
            session.add(row)
            session.flush()
        return row

    def state(self) -> Mac01StateRow:
        with self.sessions.begin() as session:
            return self._state(session)

    def set_flags(self, *, paused: bool | None = None, kill_switch: bool | None = None) -> None:
        with self.sessions.begin() as session:
            row = self._state(session)
            if paused is not None:
                row.paused = paused
            if kill_switch is not None:
                row.kill_switch = kill_switch
            row.updated_at = self.clock()

    def record_run(
        self, status: str, message: str, session_date: date | None, mode: str | None = None
    ) -> None:
        with self.sessions.begin() as session:
            row = self._state(session)
            row.last_run_at = self.clock()
            if mode is not None:
                row.last_mode = mode
            row.last_run_status = status
            row.last_run_message = message[:500]
            if session_date is not None:
                row.last_session_date = session_date
            row.updated_at = self.clock()

    def record_position(self, position: PositionSnapshot | None) -> None:
        with self.sessions.begin() as session:
            row = self._state(session)
            if position is None:
                row.position_qty = Decimal(0)
                row.position_avg_entry_price = None
                row.position_market_price = None
                row.position_unrealised_pl = Decimal(0)
            else:
                row.position_qty = position.qty
                row.position_avg_entry_price = position.avg_entry_price
                row.position_market_price = position.current_price
                row.position_unrealised_pl = position.unrealized_pl
            row.position_as_of = self.clock()
            row.updated_at = self.clock()

    def record_chart(self, chart: dict[str, Any]) -> None:
        with self.sessions.begin() as session:
            row = self._state(session)
            row.chart = chart
            row.updated_at = self.clock()

    def find_signal(
        self, strategy_version: str, symbol: str, session_date: date
    ) -> Mac01SignalRow | None:
        with self.sessions() as session:
            return session.scalar(
                select(Mac01SignalRow).where(
                    Mac01SignalRow.strategy_version == strategy_version,
                    Mac01SignalRow.symbol == symbol,
                    Mac01SignalRow.session_date == session_date,
                )
            )

    def insert_signal(self, row: Mac01SignalRow) -> tuple[Mac01SignalRow, bool]:
        """Insert once per session. On conflict, return the stored row unchanged."""

        try:
            with self.sessions.begin() as session:
                session.add(row)
            return row, True
        except IntegrityError:
            existing = self.find_signal(row.strategy_version, row.symbol, row.session_date)
            if existing is None:
                raise
            return existing, False

    def set_decision(self, signal_id: Any, decision: str, reason: str) -> None:
        with self.sessions.begin() as session:
            row = session.get(Mac01SignalRow, signal_id)
            if row is not None:
                row.decision = decision
                row.decision_reason = reason[:300]
                row.decided_at = self.clock()

    def find_order(self, client_order_id: str) -> Mac01OrderRow | None:
        with self.sessions() as session:
            return session.scalar(
                select(Mac01OrderRow).where(Mac01OrderRow.client_order_id == client_order_id)
            )

    def insert_pending_order(self, row: Mac01OrderRow) -> bool:
        """Claim the client_order_id before any broker call. False if it already exists."""

        try:
            with self.sessions.begin() as session:
                session.add(row)
            return True
        except IntegrityError:
            return False

    def non_terminal_orders(self, mode: str) -> list[Mac01OrderRow]:
        with self.sessions() as session:
            return list(
                session.scalars(
                    select(Mac01OrderRow)
                    .where(
                        Mac01OrderRow.mode == mode,
                        Mac01OrderRow.status.not_in(sorted(TERMINAL_STATUSES)),
                    )
                    .order_by(Mac01OrderRow.created_at)
                )
            )

    def orders_created_on(self, day: date, mode: str) -> int:
        local_start = datetime.combine(day, datetime.min.time(), tzinfo=NEW_YORK)
        start = local_start.astimezone(UTC)
        end = (local_start + timedelta(days=1)).astimezone(UTC)
        with self.sessions() as session:
            return int(
                session.scalar(
                    select(func.count())
                    .select_from(Mac01OrderRow)
                    .where(
                        Mac01OrderRow.mode == mode,
                        Mac01OrderRow.created_at >= start,
                        Mac01OrderRow.created_at < end,
                    )
                )
                or 0
            )

    def apply_broker_order(self, client_order_id: str, order: BrokerOrder) -> Mac01OrderRow:
        with self.sessions.begin() as session:
            row = session.scalar(
                select(Mac01OrderRow).where(Mac01OrderRow.client_order_id == client_order_id)
            )
            if row is None:
                raise LookupError(client_order_id)
            row.broker_order_id = order.id
            row.status = order.status
            row.filled_qty = order.filled_qty if row.qty is None else min(order.filled_qty, row.qty)
            row.filled_avg_price = order.filled_avg_price if order.filled_qty > 0 else None
            row.submitted_at = order.submitted_at or row.submitted_at
            row.updated_at = self.clock()
            row.last_error = None
            return row

    def mark_order(self, client_order_id: str, status: str, error: str | None) -> None:
        with self.sessions.begin() as session:
            row = session.scalar(
                select(Mac01OrderRow).where(Mac01OrderRow.client_order_id == client_order_id)
            )
            if row is None:
                raise LookupError(client_order_id)
            row.status = status
            row.last_error = error[:500] if error else None
            row.updated_at = self.clock()

    def recent_signals(self, limit: int = 100) -> list[Mac01SignalRow]:
        with self.sessions() as session:
            return list(
                session.scalars(
                    select(Mac01SignalRow).order_by(Mac01SignalRow.session_date.desc()).limit(limit)
                )
            )

    def all_orders(self) -> list[Mac01OrderRow]:
        with self.sessions() as session:
            return list(
                session.scalars(select(Mac01OrderRow).order_by(Mac01OrderRow.created_at.desc()))
            )


class AdvisoryLock:
    """Single-instance guard using a Postgres session advisory lock."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self.connection: Connection | None = None

    def acquire(self) -> bool:
        if self.engine.dialect.name != "postgresql":
            return True
        connection = self.engine.connect()
        got = connection.execute(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": ADVISORY_LOCK_KEY}
        ).scalar()
        if not got:
            connection.close()
            return False
        self.connection = connection
        return True

    def release(self) -> None:
        if self.connection is None:
            return
        try:
            self.connection.execute(
                text("SELECT pg_advisory_unlock(:key)"), {"key": ADVISORY_LOCK_KEY}
            )
            self.connection.commit()
        finally:
            self.connection.close()
            self.connection = None
