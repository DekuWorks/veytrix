"""Offline MAC-01 test harness: SQLite ledger, fake broker, fixture calendar. No network."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from veytrix_api.models import Base, Mac01OrderRow, Mac01SignalRow, Mac01StateRow
from veytrix_quant.mac01.alpaca_trading import (
    AccountSnapshot,
    AssetFlags,
    BrokerOrder,
    BrokerTimeout,
    OrderRequest,
    PositionSnapshot,
)
from veytrix_quant.mac01.config import LIVE_CONFIRM_PHRASE, Mac01Config, TradingEnvironment
from veytrix_quant.mac01.data import FixtureCalendar, FixtureMarketData, bars_from_closes
from veytrix_quant.mac01.engine import Mac01Engine
from veytrix_quant.mac01.ledger import Ledger

ACCOUNT_NUMBER = "PA3TESTACCT01"
HOLIDAYS = (date(2026, 9, 7), date(2026, 7, 3), date(2026, 11, 26))
# Monday 9 November 2026, 09:35 New York (EST, UTC-5). Friday 6 November is the signal session.
RUN_AT = datetime(2026, 11, 9, 14, 35, tzinfo=UTC)
# Friday 6 November 2026, 16:30 New York: after the close, before the next open.
AFTER_CLOSE = datetime(2026, 11, 6, 21, 30, tzinfo=UTC)
LAST_SESSION = date(2026, 11, 6)
MAC01_TABLES = [
    Base.metadata.tables[name] for name in ("mac01_signals", "mac01_orders", "mac01_state")
]


def config(**overrides: Any) -> Mac01Config:
    values: dict[str, Any] = {
        "symbol": "AAPL",
        "strategy": "sma_crossover",
        "strategy_version": "mac-01.3",
        "fast_period": 20,
        "slow_period": 50,
        "history_trading_days": 100,
        "timeframe": "1d",
        "long_only": True,
        "allow_short_selling": False,
        "broker": "alpaca_trading_api",
        "mode": "paper",
        "live_enabled": False,
        "expected_account_number": "",
        "submit_orders": True,
        "max_notional_per_trade": "100.00",
        "max_position_notional": "100.00",
        "max_orders_per_day": 2,
        "daily_loss_cutoff_usd": "20.00",
        "kill_switch": False,
        "data_feed": "iex",
    }
    values.update(overrides)
    return Mac01Config.model_validate(values)


def live_config(**overrides: Any) -> Mac01Config:
    values: dict[str, Any] = {
        "mode": "live",
        "live_enabled": True,
        "expected_account_number": ACCOUNT_NUMBER,
        "submit_orders": True,
    }
    values.update(overrides)
    return config(**values)


def trading_env(**overrides: Any) -> TradingEnvironment:
    values: dict[str, Any] = {
        "paper_api_key": SecretStr("PK" + "TESTPAPERKEY0001"),
        "paper_secret_key": SecretStr("paper-secret-" + "x" * 20),
        "live_api_key": SecretStr("AK" + "TESTLIVEKEY00001"),
        "live_secret_key": SecretStr("live-secret-" + "y" * 20),
        "live_confirm": SecretStr(LIVE_CONFIRM_PHRASE),
    }
    values.update(overrides)
    return TradingEnvironment(_env_file=None, **values)


def sqlite_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=MAC01_TABLES)
    return engine


def calendar() -> FixtureCalendar:
    return FixtureCalendar(holidays=HOLIDAYS)


def completed_sessions(count: int = 100, through: date = LAST_SESSION):
    sessions = calendar().sessions(date(2026, 1, 1), through)
    return sessions[-count:]


def closes_for(kind: str, count: int = 100) -> list[Decimal]:
    """flat ends at 100; BUY/SELL make the last close cross from equality."""

    base = [Decimal(100)] * (count - 1)
    if kind == "BUY":
        return [*base, Decimal(110)]
    if kind == "SELL":
        return [*base, Decimal(90)]
    return [*base, Decimal(100)]


def market_data(kind: str = "BUY", through: date = LAST_SESSION) -> FixtureMarketData:
    sessions = completed_sessions(100, through)
    return FixtureMarketData(bars_from_closes(sessions, closes_for(kind)))


def account(**overrides: Any) -> AccountSnapshot:
    values: dict[str, Any] = {
        "account_number": ACCOUNT_NUMBER,
        "status": "ACTIVE",
        "trading_blocked": False,
        "account_blocked": False,
        "cash": Decimal(500),
        "buying_power": Decimal(500),
        "equity": Decimal(500),
        "last_equity": Decimal(500),
    }
    values.update(overrides)
    return AccountSnapshot(**values)


def broker_order(
    client_order_id: str,
    side: str = "buy",
    status: str = "accepted",
    filled_qty: str = "0",
    filled_avg_price: str | None = None,
    notional: str | None = "100.00",
    qty: str | None = None,
) -> BrokerOrder:
    return BrokerOrder(
        id="broker-" + client_order_id[-8:],
        client_order_id=client_order_id,
        symbol="AAPL",
        side=side,
        qty=Decimal(qty) if qty else None,
        notional=Decimal(notional) if notional and side == "buy" else None,
        status=status,
        filled_qty=Decimal(filled_qty),
        filled_avg_price=Decimal(filled_avg_price) if filled_avg_price else None,
        submitted_at=RUN_AT,
    )


@dataclass
class FakeBroker:
    mode: str = "paper"
    account_snapshot: AccountSnapshot = field(default_factory=account)
    position: PositionSnapshot | None = None
    open_orders: list[BrokerOrder] = field(default_factory=list)
    asset: AssetFlags = field(default_factory=lambda: AssetFlags(True, True))
    submit_error: Exception | None = None
    submit_status: str = "accepted"
    orders_by_client_id: dict[str, BrokerOrder] = field(default_factory=dict)
    lookup_error: Exception | None = None
    account_error: Exception | None = None
    submitted: list[OrderRequest] = field(default_factory=list)
    lookups: list[str] = field(default_factory=list)
    account_calls: int = 0

    def get_account(self) -> AccountSnapshot:
        self.account_calls += 1
        if self.account_error is not None:
            raise self.account_error
        return self.account_snapshot

    def get_position(self, symbol: str) -> PositionSnapshot | None:
        assert symbol == "AAPL"
        return self.position

    def asset_flags(self, symbol: str) -> AssetFlags:
        return self.asset

    def list_open_orders(self, symbol: str) -> list[BrokerOrder]:
        return list(self.open_orders)

    def submit_order(self, request: OrderRequest) -> BrokerOrder:
        self.submitted.append(request)
        if self.submit_error is not None:
            raise self.submit_error
        order = broker_order(
            request.client_order_id,
            request.side,
            self.submit_status,
            notional=format(request.notional, "f") if request.notional else None,
            qty=format(request.qty, "f") if request.qty else None,
        )
        self.orders_by_client_id[request.client_order_id] = order
        return order

    def get_order_by_client_order_id(self, client_order_id: str) -> BrokerOrder | None:
        self.lookups.append(client_order_id)
        if self.lookup_error is not None:
            raise self.lookup_error
        return self.orders_by_client_id.get(client_order_id)


class TimeoutAfterAccepting(FakeBroker):
    """The broker accepts the order but the response is lost."""

    def submit_order(self, request: OrderRequest) -> BrokerOrder:
        self.submitted.append(request)
        self.orders_by_client_id[request.client_order_id] = broker_order(
            request.client_order_id, request.side, "accepted"
        )
        raise BrokerTimeout("Timed out submitting the order. Outcome unknown.")


def position(
    qty: str = "0.5", available: str | None = None, side: str = "long"
) -> PositionSnapshot:
    return PositionSnapshot(
        symbol="AAPL",
        side=side,
        qty=Decimal(qty),
        qty_available=Decimal(available if available is not None else qty),
        avg_entry_price=Decimal("100"),
        current_price=Decimal("101"),
        market_value=Decimal(qty) * Decimal("101"),
        unrealized_pl=Decimal(qty) * Decimal("1"),
    )


def make_engine(
    engine,
    broker: FakeBroker,
    *,
    kind: str = "BUY",
    submit_flag: bool = True,
    now: datetime = RUN_AT,
    data: FixtureMarketData | None = None,
    cfg: Mac01Config | None = None,
    env: TradingEnvironment | None = None,
    secrets: tuple[str, ...] = (),
    **config_overrides: Any,
) -> Mac01Engine:
    return Mac01Engine(
        cfg or config(**config_overrides),
        broker,
        data or market_data(kind),
        calendar(),
        Ledger(engine, clock=lambda: now),
        submit_flag=submit_flag,
        env=env or trading_env(),
        clock=lambda: now,
        secrets=secrets,
    )


def orders(engine) -> list[Mac01OrderRow]:
    return Ledger(engine).all_orders()


def signals(engine) -> list[Mac01SignalRow]:
    return Ledger(engine).recent_signals()


def state(engine) -> Mac01StateRow:
    return Ledger(engine).state()
