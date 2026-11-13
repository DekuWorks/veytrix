"""Postgres baseline. Prices are not seeded; the sample series stays in memory."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from veytrix_risk.sizing import RiskPolicy


class Base(DeclarativeBase):
    pass


class Money(TypeDecorator):
    """Decimal amount. SQLite keeps the text so a test does not pick up float dust."""

    impl = Numeric(36, 18)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "sqlite":
            return dialect.type_descriptor(String(80))
        return dialect.type_descriptor(Numeric(36, 18))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        amount = value if isinstance(value, Decimal) else Decimal(str(value))
        if dialect.name == "sqlite":
            return format(amount, "f")
        return amount

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return Decimal(str(value))


class Instrument(Base):
    __tablename__ = "instruments"
    __table_args__ = (UniqueConstraint("venue", "symbol", name="uq_instruments_venue_symbol"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False)
    venue: Mapped[str] = mapped_column(String(32), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    contract_multiplier: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    tick_size: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    calendar: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PriceBar(Base):
    __tablename__ = "price_bars"
    __table_args__ = (
        UniqueConstraint("instrument_id", "bar_start", name="uq_price_bars_instrument_bar_start"),
        CheckConstraint(
            "high >= low AND high >= open AND high >= close AND low <= open AND low <= close",
            name="ck_price_bars_ohlc",
        ),
        CheckConstraint("volume >= 0", name="ck_price_bars_volume"),
        CheckConstraint(
            "open > 0 AND high > 0 AND low > 0 AND close > 0",
            name="ck_price_bars_positive",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("instruments.id", name="fk_price_bars_instrument_id"),
        nullable=False,
    )
    bar_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    open: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    volume: Mapped[Decimal] = mapped_column(Numeric(24, 4), nullable=False)
    source_id: Mapped[str] = mapped_column(String(64), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class RiskPolicyRow(Base):
    __tablename__ = "risk_policies"
    __table_args__ = (
        UniqueConstraint("name", name="uq_risk_policies_name"),
        CheckConstraint("trading_mode = 'paper'", name="ck_risk_policies_paper_only"),
        CheckConstraint("experimental", name="ck_risk_policies_experimental"),
        CheckConstraint(
            "daily_stop_enforced = false AND weekly_stop_enforced = false",
            name="ck_risk_policies_stops_not_enforced",
        ),
        CheckConstraint(
            "per_trade_risk_fraction > 0 AND per_trade_risk_fraction <= 0.02",
            name="ck_risk_policies_per_trade",
        ),
        CheckConstraint(
            "daily_loss_stop_fraction > 0 AND daily_loss_stop_fraction <= 0.02",
            name="ck_risk_policies_daily",
        ),
        CheckConstraint(
            "weekly_loss_stop_fraction > 0 AND weekly_loss_stop_fraction <= 0.05",
            name="ck_risk_policies_weekly",
        ),
        CheckConstraint(
            "max_allocation_fraction > 0 AND max_allocation_fraction <= 0.10",
            name="ck_risk_policies_allocation",
        ),
        CheckConstraint("risk_fraction_ceiling = 0.02", name="ck_risk_policies_ceiling"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    experimental: Mapped[bool] = mapped_column(Boolean, nullable=False)
    trading_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    per_trade_risk_fraction: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    daily_loss_stop_fraction: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    weekly_loss_stop_fraction: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    max_allocation_fraction: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    risk_fraction_ceiling: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    daily_stop_enforced: Mapped[bool] = mapped_column(Boolean, nullable=False)
    weekly_stop_enforced: Mapped[bool] = mapped_column(Boolean, nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def to_domain(self) -> RiskPolicy:
        return RiskPolicy(
            name=self.name,
            per_trade_risk_fraction=self.per_trade_risk_fraction,
            daily_loss_stop_fraction=self.daily_loss_stop_fraction,
            weekly_loss_stop_fraction=self.weekly_loss_stop_fraction,
            max_allocation_fraction=self.max_allocation_fraction,
            risk_fraction_ceiling=self.risk_fraction_ceiling,
            daily_stop_enforced=self.daily_stop_enforced,
            weekly_stop_enforced=self.weekly_stop_enforced,
            experimental=self.experimental,
            trading_mode=self.trading_mode,
        )


class PaperPositionRow(Base):
    """A saved paper size. This is not a fill and has no broker identity."""

    __tablename__ = "paper_positions"
    __table_args__ = (
        CheckConstraint(
            "symbol IN ('BTC-USD', 'ETH-USD', 'SOL-USD')",
            name="ck_paper_positions_symbol",
        ),
        CheckConstraint("entry > 0", name="ck_paper_positions_entry"),
        CheckConstraint("stop > 0", name="ck_paper_positions_stop"),
        CheckConstraint("shares >= 0", name="ck_paper_positions_shares"),
        CheckConstraint("notional >= 0", name="ck_paper_positions_notional"),
        CheckConstraint("planned_risk >= 0", name="ck_paper_positions_planned_risk"),
        CheckConstraint(
            "binding_constraint IN ('risk', 'allocation', 'both', 'none')",
            name="ck_paper_positions_binding",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False)
    entry: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    stop: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    shares: Mapped[int] = mapped_column(Integer, nullable=False)
    notional: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    planned_risk: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    binding_constraint: Mapped[str] = mapped_column(String(16), nullable=False)
    exchange_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ResearchNoteRow(Base):
    """A private research note. This is not an instruction to trade."""

    __tablename__ = "research_notes"
    __table_args__ = (
        CheckConstraint(
            "char_length(title) BETWEEN 1 AND 120",
            name="ck_research_notes_title",
        ),
        CheckConstraint(
            "char_length(body) BETWEEN 1 AND 4000",
            name="ck_research_notes_body",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SourceEventRow(Base):
    """A source event the user typed. This is not news and not an order."""

    __tablename__ = "source_events"
    __table_args__ = (
        CheckConstraint(
            "char_length(title) BETWEEN 1 AND 120",
            name="ck_source_events_title",
        ),
        CheckConstraint(
            "char_length(source) BETWEEN 1 AND 200",
            name="ck_source_events_source",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    source: Mapped[str] = mapped_column(String(200), nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    first_public_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PaperSizeJournalRow(Base):
    """One successful paper size. This is not an order and has no broker identity."""

    __tablename__ = "paper_size_journal"
    __table_args__ = (
        CheckConstraint(
            "symbol IN ('BTC-USD', 'ETH-USD', 'SOL-USD')",
            name="ck_paper_size_journal_symbol",
        ),
        CheckConstraint("equity > 0", name="ck_paper_size_journal_equity"),
        CheckConstraint("entry > 0", name="ck_paper_size_journal_entry"),
        CheckConstraint("stop > 0", name="ck_paper_size_journal_stop"),
        CheckConstraint("stop < entry", name="ck_paper_size_journal_long_stop"),
        CheckConstraint("shares >= 0", name="ck_paper_size_journal_shares"),
        CheckConstraint("planned_risk >= 0", name="ck_paper_size_journal_planned_risk"),
        CheckConstraint(
            "binding_constraint IN ('risk', 'allocation', 'both', 'none')",
            name="ck_paper_size_journal_binding",
        ),
        CheckConstraint(
            "execution_permitted = false AND order_submitted = false",
            name="ck_paper_size_journal_not_an_order",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    symbol: Mapped[str] = mapped_column(String(16), nullable=False)
    equity: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    entry: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    stop: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    shares: Mapped[int] = mapped_column(Integer, nullable=False)
    planned_risk: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    binding_constraint: Mapped[str] = mapped_column(String(16), nullable=False)
    execution_permitted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    order_submitted: Mapped[bool] = mapped_column(Boolean, nullable=False)


MAC01_SIDES = ("BUY", "SELL", "HOLD")
MAC01_ORDER_SIDES = ("buy", "sell")


class Mac01SignalRow(Base):
    """One MAC-01 signal per completed session. A signal is not an order."""

    __tablename__ = "mac01_signals"
    __table_args__ = (
        UniqueConstraint(
            "strategy_version", "symbol", "session_date", name="uq_mac01_signals_session"
        ),
        CheckConstraint("symbol = 'AAPL'", name="ck_mac01_signals_symbol"),
        CheckConstraint("side IN ('BUY', 'SELL', 'HOLD')", name="ck_mac01_signals_side"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    strategy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False)
    session_date: Mapped[date] = mapped_column(Date, nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    fast_prev: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    slow_prev: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    fast_cur: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    slow_cur: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    reason: Mapped[str] = mapped_column(String(200), nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    decision_reason: Mapped[str] = mapped_column(String(300), nullable=False)
    inputs_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Mac01OrderRow(Base):
    """A MAC-01 order sent, or about to be sent, to the user's Alpaca Trading API account."""

    __tablename__ = "mac01_orders"
    __table_args__ = (
        UniqueConstraint("client_order_id", name="uq_mac01_orders_client_order_id"),
        CheckConstraint("symbol = 'AAPL'", name="ck_mac01_orders_symbol"),
        CheckConstraint("mode IN ('paper', 'live')", name="ck_mac01_orders_mode"),
        CheckConstraint(
            "(side = 'buy' AND notional IS NOT NULL AND qty IS NULL "
            "AND notional > 0 AND notional <= 100) "
            "OR (side = 'sell' AND qty IS NOT NULL AND notional IS NULL AND qty > 0)",
            name="ck_mac01_orders_sizing",
        ),
        CheckConstraint("filled_qty >= 0", name="ck_mac01_orders_filled"),
        CheckConstraint("order_type = 'market'", name="ck_mac01_orders_type"),
        CheckConstraint("time_in_force = 'day'", name="ck_mac01_orders_tif"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_order_id: Mapped[str] = mapped_column(String(128), nullable=False)
    mode: Mapped[str] = mapped_column(String(8), nullable=False)
    strategy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False)
    session_date: Mapped[date] = mapped_column(Date, nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    notional: Mapped[Decimal | None] = mapped_column(Numeric(24, 2), nullable=True)
    qty: Mapped[Decimal | None] = mapped_column(Numeric(24, 9), nullable=True)
    order_type: Mapped[str] = mapped_column(String(16), nullable=False)
    time_in_force: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    broker_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    filled_qty: Mapped[Decimal] = mapped_column(Numeric(24, 9), nullable=False)
    filled_avg_price: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)


class Mac01StateRow(Base):
    """Single MAC-01 control and health row. Position fields are the last broker snapshot."""

    __tablename__ = "mac01_state"
    __table_args__ = (CheckConstraint("id = 1", name="ck_mac01_state_singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    paused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    kill_switch: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_run_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_session_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_mode: Mapped[str | None] = mapped_column(String(8), nullable=True)
    position_qty: Mapped[Decimal | None] = mapped_column(Numeric(24, 9), nullable=True)
    position_avg_entry_price: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    position_market_price: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    position_unrealised_pl: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    position_as_of: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    chart: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class BlockchainNetworkRow(Base):
    """A testnet the paper-swap CLI is allowed to price. No keys, no mainnet."""

    __tablename__ = "blockchain_networks"
    __table_args__ = (
        UniqueConstraint("name", name="uq_blockchain_networks_name"),
        CheckConstraint(
            "name IN ('solana', 'ethereum', 'base')",
            name="ck_blockchain_networks_name",
        ),
        CheckConstraint(
            "network IN ('solana-devnet', 'sepolia', 'base-sepolia')",
            name="ck_blockchain_networks_network",
        ),
        CheckConstraint(
            "chain_id IN ('devnet', '11155111', '84532')",
            name="ck_blockchain_networks_chain",
        ),
        CheckConstraint("simulated", name="ck_blockchain_networks_simulated"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(16), nullable=False)
    network: Mapped[str] = mapped_column(String(32), nullable=False)
    chain_id: Mapped[str] = mapped_column(String(16), nullable=False)
    simulated: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SimulatedWalletBalanceRow(Base):
    """Simulated token balance. This is not an on-chain wallet."""

    __tablename__ = "simulated_wallet_balances"
    __table_args__ = (
        UniqueConstraint(
            "network_id", "symbol", name="uq_simulated_wallet_balances_network_symbol"
        ),
        CheckConstraint("amount >= 0", name="ck_simulated_wallet_balances_amount"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    network_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("blockchain_networks.id", name="fk_simulated_wallet_balances_network_id"),
        nullable=False,
    )
    symbol: Mapped[str] = mapped_column(String(16), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Money(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PaperSwapOrderRow(Base):
    """A simulated swap recorded by the CLI. The API does not insert these."""

    __tablename__ = "paper_swap_orders"
    __table_args__ = (
        CheckConstraint("status = 'simulated'", name="ck_paper_swap_orders_status"),
        CheckConstraint("simulated", name="ck_paper_swap_orders_simulated"),
        CheckConstraint("amount_in > 0", name="ck_paper_swap_orders_amount_in"),
        CheckConstraint("quoted_out > 0", name="ck_paper_swap_orders_quoted_out"),
        CheckConstraint("amount_out > 0", name="ck_paper_swap_orders_amount_out"),
        CheckConstraint("quoted_price > 0", name="ck_paper_swap_orders_price"),
        CheckConstraint("slippage_bps BETWEEN 1 AND 500", name="ck_paper_swap_orders_slippage"),
        CheckConstraint("slippage_applied >= 0", name="ck_paper_swap_orders_slippage_applied"),
        CheckConstraint("fee_estimate >= 0", name="ck_paper_swap_orders_fee"),
        CheckConstraint(
            "price_kind IN ('pool', 'reference')",
            name="ck_paper_swap_orders_price_kind",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    network_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("blockchain_networks.id", name="fk_paper_swap_orders_network_id"),
        nullable=False,
    )
    token_in: Mapped[str] = mapped_column(String(16), nullable=False)
    token_out: Mapped[str] = mapped_column(String(16), nullable=False)
    amount_in: Mapped[Decimal] = mapped_column(Money(), nullable=False)
    quoted_out: Mapped[Decimal] = mapped_column(Money(), nullable=False)
    amount_out: Mapped[Decimal] = mapped_column(Money(), nullable=False)
    quoted_price: Mapped[Decimal] = mapped_column(Money(), nullable=False)
    slippage_bps: Mapped[int] = mapped_column(Integer, nullable=False)
    slippage_applied: Mapped[Decimal] = mapped_column(Money(), nullable=False)
    fee_estimate: Mapped[Decimal] = mapped_column(Money(), nullable=False)
    fee_symbol: Mapped[str] = mapped_column(String(16), nullable=False)
    quote_source: Mapped[str] = mapped_column(String(64), nullable=False)
    price_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    simulated: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PaperSwapFillRow(Base):
    """The simulated fill for one paper swap, including the balances afterwards."""

    __tablename__ = "paper_swap_fills"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_paper_swap_fills_order_id"),
        CheckConstraint("simulated", name="ck_paper_swap_fills_simulated"),
        CheckConstraint("amount_in > 0", name="ck_paper_swap_fills_amount_in"),
        CheckConstraint("amount_out > 0", name="ck_paper_swap_fills_amount_out"),
        CheckConstraint("fee_estimate >= 0", name="ck_paper_swap_fills_fee"),
        CheckConstraint("slippage_applied >= 0", name="ck_paper_swap_fills_slippage"),
        CheckConstraint("quoted_price > 0", name="ck_paper_swap_fills_price"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("paper_swap_orders.id", name="fk_paper_swap_fills_order_id"),
        nullable=False,
    )
    amount_in: Mapped[Decimal] = mapped_column(Money(), nullable=False)
    amount_out: Mapped[Decimal] = mapped_column(Money(), nullable=False)
    fee_estimate: Mapped[Decimal] = mapped_column(Money(), nullable=False)
    slippage_applied: Mapped[Decimal] = mapped_column(Money(), nullable=False)
    quoted_price: Mapped[Decimal] = mapped_column(Money(), nullable=False)
    quote_source: Mapped[str] = mapped_column(String(64), nullable=False)
    simulated: Mapped[bool] = mapped_column(Boolean, nullable=False)
    balances_after: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AuditEvent(Base):
    """Append-only request audit. Triggers in migration 0009 reject updates and deletes."""

    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_correlation_id", "correlation_id"),
        Index("ix_audit_events_created_at", "created_at"),
        CheckConstraint(
            "char_length(correlation_id) BETWEEN 1 AND 64",
            name="ck_audit_events_correlation_id",
        ),
        CheckConstraint(
            "char_length(action) BETWEEN 1 AND 128",
            name="ck_audit_events_action",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AgentRow(Base):
    """A desk name in the local registry. Not a running process and not an order path."""

    __tablename__ = "agents"
    __table_args__ = (
        UniqueConstraint("code", name="uq_agents_code"),
        CheckConstraint(
            "code IN ("
            "'SUPERVISOR-01', 'DAY-01', 'STOCK-01', 'CRYPTO-01', 'DEFI-01', "
            "'ETF-01', 'FUTURES-01', 'RESEARCH-01', 'RISK-01', 'TREASURY-01'"
            ")",
            name="ck_agents_code",
        ),
        CheckConstraint(
            "status IN ('disabled', 'paused', 'enabled')",
            name="ck_agents_status",
        ),
        CheckConstraint("paper_only", name="ck_agents_paper_only"),
        CheckConstraint("can_submit_orders = false", name="ck_agents_cannot_submit"),
        CheckConstraint("can_sign = false", name="ck_agents_cannot_sign"),
        CheckConstraint("can_transfer_funds = false", name="ck_agents_cannot_transfer"),
        CheckConstraint("holds_credentials = false", name="ck_agents_no_credentials"),
        CheckConstraint(
            "char_length(display_name) BETWEEN 1 AND 64",
            name="ck_agents_display_name",
        ),
        CheckConstraint("char_length(notes) BETWEEN 1 AND 500", name="ck_agents_notes"),
        {"schema": "private"},
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str] = mapped_column(String(64), nullable=False)
    desk: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    paper_only: Mapped[bool] = mapped_column(Boolean, nullable=False)
    can_submit_orders: Mapped[bool] = mapped_column(Boolean, nullable=False)
    can_sign: Mapped[bool] = mapped_column(Boolean, nullable=False)
    can_transfer_funds: Mapped[bool] = mapped_column(Boolean, nullable=False)
    holds_credentials: Mapped[bool] = mapped_column(Boolean, nullable=False)
    notes: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AgentPermissionRow(Base):
    """An explicit deny. The effect column cannot be anything except deny."""

    __tablename__ = "agent_permissions"
    __table_args__ = (
        UniqueConstraint("agent_id", "tool_name", name="uq_agent_permissions_agent_tool"),
        CheckConstraint("effect = 'deny'", name="ck_agent_permissions_effect"),
        CheckConstraint(
            "tool_name IN ("
            "'submit_order', 'cancel_order', 'sign_transaction', 'broadcast_transaction', "
            "'bank_transfer', 'set_live_mode', 'release_kill_switch'"
            ")",
            name="ck_agent_permissions_tool",
        ),
        Index("ix_agent_permissions_agent_id", "agent_id"),
        {"schema": "private"},
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("private.agents.id", name="fk_agent_permissions_agent_id"),
        nullable=False,
    )
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False)
    effect: Mapped[str] = mapped_column(String(8), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AgentRunRow(Base):
    """One finished registry run. Not a broker fill. Rows are append-only."""

    __tablename__ = "agent_runs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_agent_runs_idempotency_key"),
        CheckConstraint(
            "status IN ('recorded', 'failed', 'skipped')",
            name="ck_agent_runs_status",
        ),
        CheckConstraint("finished_at >= started_at", name="ck_agent_runs_window"),
        CheckConstraint(
            "char_length(idempotency_key) BETWEEN 1 AND 128",
            name="ck_agent_runs_idempotency",
        ),
        CheckConstraint(
            "char_length(correlation_id) BETWEEN 1 AND 64",
            name="ck_agent_runs_correlation",
        ),
        CheckConstraint("char_length(summary) BETWEEN 1 AND 500", name="ck_agent_runs_summary"),
        Index("ix_agent_runs_agent_started", "agent_id", "started_at"),
        {"schema": "private"},
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("private.agents.id", name="fk_agent_runs_agent_id"),
        nullable=False,
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ResearchTaskRow(Base):
    """A research assignment from Roads. Not an order and not a broker instruction."""

    __tablename__ = "research_tasks"
    __table_args__ = (
        CheckConstraint(
            "assignee_code IN ("
            "'SUPERVISOR-01', 'DAY-01', 'STOCK-01', 'CRYPTO-01', 'DEFI-01', "
            "'ETF-01', 'FUTURES-01', 'RESEARCH-01', 'RISK-01', 'TREASURY-01'"
            ")",
            name="ck_research_tasks_assignee",
        ),
        CheckConstraint("assigned_by = 'SUPERVISOR-01'", name="ck_research_tasks_assigner"),
        CheckConstraint(
            "status IN ('assigned', 'reported', 'blocked')",
            name="ck_research_tasks_status",
        ),
        CheckConstraint("char_length(subject) BETWEEN 1 AND 80", name="ck_research_tasks_subject"),
        CheckConstraint(
            "char_length(instruction) BETWEEN 1 AND 500",
            name="ck_research_tasks_instruction",
        ),
        Index("ix_research_tasks_assignee", "assignee_code", "created_at"),
        {"schema": "private"},
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assignee_code: Mapped[str] = mapped_column(String(32), nullable=False)
    assigned_by: Mapped[str] = mapped_column(String(32), nullable=False)
    subject: Mapped[str] = mapped_column(String(80), nullable=False)
    instruction: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("private.conversations.id", name="fk_research_tasks_conversation"),
        nullable=True,
    )
    evidence_message_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ConversationRow(Base):
    """A conversation between the user and desks, or between desks. Not an order path."""

    __tablename__ = "conversations"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('direct', 'group', 'discussion', 'boardroom')", name="ck_conversations_kind"
        ),
        CheckConstraint(
            "status IN ('open', 'paused', 'closed', 'archived')", name="ck_conversations_status"
        ),
        CheckConstraint("created_by IN ('human', 'system')", name="ck_conversations_creator"),
        CheckConstraint("max_rounds BETWEEN 0 AND 5", name="ck_conversations_rounds"),
        CheckConstraint("max_messages BETWEEN 1 AND 500", name="ck_conversations_budget"),
        CheckConstraint("char_length(title) BETWEEN 1 AND 120", name="ck_conversations_title"),
        {"schema": "private"},
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    topic: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[str] = mapped_column(String(16), nullable=False)
    max_rounds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_messages: Mapped[int] = mapped_column(Integer, nullable=False, default=200)
    owner_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    agenda: Mapped[list | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ConversationMemberRow(Base):
    __tablename__ = "conversation_members"
    __table_args__ = (
        CheckConstraint("member_kind IN ('human', 'agent')", name="ck_members_kind"),
        CheckConstraint(
            "role IN ('participant', 'moderator', 'owner', 'observer')", name="ck_members_role"
        ),
        {"schema": "private"},
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("private.conversations.id", name="fk_members_conversation"),
        primary_key=True,
    )
    member_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    member_kind: Mapped[str] = mapped_column(String(8), nullable=False)
    role: Mapped[str] = mapped_column(String(12), nullable=False)
    last_read_seq: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class MessageRow(Base):
    """One message. Append-only: a trigger in migration 0011 rejects update and delete."""

    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("conversation_id", "seq", name="uq_messages_conversation_seq"),
        CheckConstraint(
            "sender_kind IN ('human', 'agent', 'system', 'tool')", name="ck_messages_sender_kind"
        ),
        CheckConstraint(
            "origin IN ('human', 'scripted', 'model_generated', 'tool_verified', 'simulated')",
            name="ck_messages_origin",
        ),
        CheckConstraint("char_length(content) BETWEEN 1 AND 4000", name="ck_messages_content"),
        {"schema": "private"},
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("private.conversations.id", name="fk_messages_conversation"),
        nullable=False,
    )
    seq: Mapped[int] = mapped_column(BigInteger, nullable=False)
    thread_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    sender_id: Mapped[str] = mapped_column(String(32), nullable=False)
    sender_kind: Mapped[str] = mapped_column(String(8), nullable=False)
    recipient_ids: Mapped[list] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    origin: Mapped[str] = mapped_column(String(16), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decision_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tool_call_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    client_message_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="delivered")
    visibility: Mapped[str] = mapped_column(String(16), nullable=False, default="conversation")
    citations: Mapped[list] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    meta: Mapped[dict] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class MessageEventRow(Base):
    """Append-only lifecycle event for a conversation or message."""

    __tablename__ = "message_events"
    __table_args__ = {"schema": "private"}

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("private.conversations.id", name="fk_events_conversation"),
        nullable=False,
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor: Mapped[str] = mapped_column(String(32), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AgentPresenceRow(Base):
    __tablename__ = "agent_presence"
    __table_args__ = (
        CheckConstraint(
            "state IN ('idle', 'listening', 'composing', 'speaking', 'meeting')",
            name="ck_presence_state",
        ),
        {"schema": "private"},
    )

    agent_code: Mapped[str] = mapped_column(String(32), primary_key=True)
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ConversationSummaryRow(Base):
    __tablename__ = "conversation_summaries"
    __table_args__ = (
        CheckConstraint(
            "origin IN ('scripted', 'model_generated', 'tool_verified', 'simulated')",
            name="ck_summaries_origin",
        ),
        {"schema": "private"},
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("private.conversations.id", name="fk_summaries_conversation"),
        nullable=False,
    )
    upto_seq: Mapped[int] = mapped_column(BigInteger, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    origin: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
