"""Public response models. Money leaves the API as decimal strings."""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator, model_validator

from veytrix_market.coinbase import ProductId


def _decimal_string(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, str):
        raise ValueError("Send decimal values as strings, not JSON numbers.")
    return value


def _optional_decimal_string(value: object) -> str | None:
    if value is None:
        return None
    return _decimal_string(value)


DecimalText = Annotated[str, BeforeValidator(_decimal_string)]
OptionalDecimalText = Annotated[str | None, BeforeValidator(_optional_decimal_string)]


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ReadyResponse(BaseModel):
    status: Literal["ready", "unavailable"]
    database: Literal["up", "down"]


class VersionInfo(BaseModel):
    api: Literal["0.1.0"]
    python: str


class DiagnosticsResponse(BaseModel):
    service: Literal["veytrix-api"]
    env: Literal["local"]
    trading_mode: Literal["paper"]
    live_broker: Literal["disabled"]
    auth: Literal["not_configured"]
    sample_data: Literal[True]
    execution_permitted: Literal[False]
    daily_weekly_stops_enforced: Literal[False]
    rate_limit: Literal["process_local"]
    csrf: Literal["not_implemented"]
    versions: VersionInfo


class InstrumentResponse(BaseModel):
    symbol: str
    venue: str
    asset_type: str
    currency: str
    source_id: str
    name: str
    timezone: str
    calendar: str
    calendar_note: str
    tick_size: str
    contract_multiplier: str
    synthetic: bool


class InstrumentListResponse(BaseModel):
    instruments: list[InstrumentResponse]
    disclaimer: str


class BarResponse(BaseModel):
    bar_start: str
    open: str
    high: str
    low: str
    close: str
    volume: str


class BarsResponse(BaseModel):
    symbol: str
    venue: str
    asset_type: str
    currency: str
    source_id: str
    interval: Literal["1d", "1m"]
    seed: int | None = None
    synthetic: bool
    calendar_note: str
    disclaimer: str
    last_close: str | None = None
    previous_close: str | None = None
    change: str | None = None
    change_percent: str | None = None
    retrieved_at: str | None = None
    source_url: str | None = None
    bars: list[BarResponse]


class TickerResponse(BaseModel):
    symbol: ProductId
    venue: Literal["COINBASE"]
    source_id: Literal["coinbase-exchange"]
    synthetic: Literal[False]
    price: str
    bid: str
    ask: str
    size: str
    volume: str
    trade_time: str
    trade_id: int
    retrieved_at: str
    disclaimer: str


class MarketFeedHealth(BaseModel):
    """One public ticker. A down feed has no price."""

    model_config = ConfigDict(extra="forbid")

    symbol: ProductId
    status: Literal["up", "stale", "down"]
    source_id: Literal["coinbase-exchange"]
    synthetic: Literal[False]
    retrieved_at: str | None = Field(
        default=None, pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
    )
    trade_time: str | None = Field(default=None, min_length=1, max_length=64)
    age_seconds: int | None = Field(default=None, ge=0)
    price: str | None = Field(default=None, pattern=r"^(?:0|[1-9]\d*)(?:\.\d+)?$")
    note: str = Field(min_length=1, max_length=240)

    @model_validator(mode="after")
    def price_matches_status(self) -> MarketFeedHealth:
        if self.status == "down":
            leaked = (
                self.price is not None
                or self.retrieved_at is not None
                or self.age_seconds is not None
            )
            if leaked:
                raise ValueError("A down feed has no price and no timestamp.")
            return self
        if self.price is None or self.retrieved_at is None or self.age_seconds is None:
            raise ValueError("An up or stale feed includes its last print.")
        return self


class MarketHealthResponse(BaseModel):
    """Display health for the three Coinbase products. Not an order path."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "degraded", "unavailable"]
    source: Literal["coinbase-exchange"]
    stale_after_seconds: Literal[120]
    feeds: list[MarketFeedHealth] = Field(min_length=3, max_length=3)
    sample_included: Literal[False]
    executable: Literal[False]
    execution_permitted: Literal[False]
    order_submitted: Literal[False]
    order_route: Literal["absent"]
    note: str = Field(min_length=1, max_length=400)

    @model_validator(mode="after")
    def status_matches_feeds(self) -> MarketHealthResponse:
        symbols = [feed.symbol for feed in self.feeds]
        if symbols != ["BTC-USD", "ETH-USD", "SOL-USD"]:
            raise ValueError("Feeds stay in the display order.")
        statuses = [feed.status for feed in self.feeds]
        if all(status == "up" for status in statuses):
            expected = "ok"
        elif all(status == "down" for status in statuses):
            expected = "unavailable"
        else:
            expected = "degraded"
        if self.status != expected:
            raise ValueError("Overall status does not match the feeds.")
        return self


class SizeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: ProductId
    account_equity: DecimalText = Field(examples=["100000.00"])
    entry_price: DecimalText = Field(examples=["50.00"])
    stop_price: DecimalText = Field(examples=["48.00"])
    side: Literal["long"] = "long"
    risk_fraction: OptionalDecimalText = None
    max_allocation_fraction: OptionalDecimalText = None


class SizeResponse(BaseModel):
    symbol: ProductId
    shares: int
    binding_constraint: Literal["risk", "allocation", "both", "none"]
    stop_distance: str
    planned_risk_amount: str
    risk_budget: str
    notional: str
    account_equity: str
    entry_price: str
    stop_price: str
    risk_fraction: str
    max_allocation_fraction: str
    daily_loss_stop_fraction: str
    weekly_loss_stop_fraction: str
    policy_name: str
    warning: str | None
    note: str
    execution_permitted: Literal[False]
    order_submitted: Literal[False]
    daily_stop_enforced: Literal[False]
    weekly_stop_enforced: Literal[False]


class ShieldPreviewRequest(BaseModel):
    """A hypothetical buy. This body cannot submit an order."""

    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(pattern=r"^[A-Z][A-Z0-9.-]{0,15}$")
    side: Literal["long", "short"]
    limit_price: DecimalText
    quantity: DecimalText
    position_notional: DecimalText
    orders_today: int = Field(ge=0, le=10000)
    quote_age_seconds: int = Field(ge=0, le=8640000)
    leverage: DecimalText


class OutstandingReservation(BaseModel):
    """One caller-supplied row. This model does not write it."""

    model_config = ConfigDict(extra="forbid")

    agent: str = Field(min_length=1, max_length=32)
    notional: DecimalText
    idempotency_key: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,63}$")


class ReservationPreviewRequest(BaseModel):
    """A hypothetical reservation. This body cannot submit an order."""

    model_config = ConfigDict(extra="forbid")

    agent: str = Field(min_length=1, max_length=32)
    notional: DecimalText
    idempotency_key: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,63}$")
    outstanding: list[OutstandingReservation] = Field(default_factory=list, max_length=9)


class ReservationPreviewResponse(BaseModel):
    """The local book check. Nothing is reserved and release stays withheld."""

    model_config = ConfigDict(extra="forbid")

    policy_version: Literal["local-2026-11-08"]
    rule_result: Literal["pass", "fail"]
    reasons: list[str] = Field(max_length=3)
    requested: str = Field(pattern=r"^(?:0|[1-9]\d*)(?:\.\d+)?$")
    reserved_before: str = Field(pattern=r"^(?:0|[1-9]\d*)(?:\.\d+)?$")
    reserved_after: str = Field(pattern=r"^(?:0|[1-9]\d*)(?:\.\d+)?$")
    book_cap: Literal["100.00"]
    release: Literal["withheld"]
    persisted: Literal[False]
    lock: Literal["absent"]
    buying_power_checked: Literal[False]
    broker_reconciled: Literal[False]
    owner_approved: Literal[False]
    execution_permitted: Literal[False]
    order_submitted: Literal[False]
    note: str = Field(min_length=1, max_length=400)

    @model_validator(mode="after")
    def reasons_match_result(self) -> ReservationPreviewResponse:
        known = ("agent", "idempotency", "book")
        if any(reason not in known for reason in self.reasons):
            raise ValueError("Unknown reservation reason.")
        ordered = [reason for reason in known if reason in self.reasons]
        if self.reasons != ordered:
            raise ValueError("Reservation reasons are out of order.")
        if self.rule_result == "pass" and self.reasons:
            raise ValueError("A passing preview has no reasons.")
        if self.rule_result == "fail" and not self.reasons:
            raise ValueError("A failing preview names a reason.")
        return self


class ShieldPreviewResponse(BaseModel):
    """The local rule result. Release stays withheld."""

    model_config = ConfigDict(extra="forbid")

    policy_version: Literal["local-2026-11-08"]
    rule_result: Literal["pass", "fail"]
    reasons: list[str] = Field(max_length=7)
    notional: str = Field(pattern=r"^(?:0|[1-9]\d*)(?:\.\d+)?$")
    position_after: str = Field(pattern=r"^(?:0|[1-9]\d*)(?:\.\d+)?$")
    max_notional: Literal["100.00"]
    max_position_notional: Literal["100.00"]
    max_orders_per_day: Literal[2]
    quote_max_age_seconds: Literal[120]
    release: Literal["withheld"]
    buying_power_checked: Literal[False]
    owner_approved: Literal[False]
    broker_reconciled: Literal[False]
    execution_permitted: Literal[False]
    order_submitted: Literal[False]
    note: str = Field(min_length=1, max_length=400)

    @model_validator(mode="after")
    def reasons_match_result(self) -> ShieldPreviewResponse:
        known = (
            "short",
            "leverage",
            "symbol",
            "stale",
            "notional",
            "position",
            "daily_orders",
        )
        if any(reason not in known for reason in self.reasons):
            raise ValueError("Unknown shield reason.")
        ordered = [reason for reason in known if reason in self.reasons]
        if self.reasons != ordered:
            raise ValueError("Shield reasons are out of order.")
        if self.rule_result == "pass" and self.reasons:
            raise ValueError("A passing preview has no reasons.")
        if self.rule_result == "fail" and not self.reasons:
            raise ValueError("A failing preview names a reason.")
        return self


def _finite_decimal(value: str, label: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"{label} must be a decimal string.") from exc
    if not parsed.is_finite():
        raise ValueError(f"{label} must be a finite decimal.")
    return parsed


class PaperPositionCreate(BaseModel):
    """A size the caller already calculated. This body does not place an order."""

    model_config = ConfigDict(extra="forbid")

    symbol: ProductId
    entry: DecimalText
    stop: DecimalText
    shares: int = Field(ge=0)
    notional: DecimalText
    planned_risk: DecimalText
    binding_constraint: Literal["risk", "allocation", "both", "none"]
    exchange_time: str

    @field_validator("exchange_time")
    @classmethod
    def exchange_time_is_zoned(cls, value: str) -> str:
        if "T" not in value:
            raise ValueError("Exchange time must be an ISO-8601 timestamp.")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("Exchange time must be an ISO-8601 timestamp.") from exc
        if parsed.tzinfo is None:
            raise ValueError("Exchange time must include a timezone.")
        return value

    @model_validator(mode="after")
    def money_matches_a_long_paper_size(self) -> PaperPositionCreate:
        entry = _finite_decimal(self.entry, "Entry")
        stop = _finite_decimal(self.stop, "Stop")
        notional = _finite_decimal(self.notional, "Notional")
        planned_risk = _finite_decimal(self.planned_risk, "Planned risk")
        if entry <= 0 or stop <= 0:
            raise ValueError("Entry and stop must be positive.")
        if notional < 0 or planned_risk < 0:
            raise ValueError("Notional and planned risk cannot be negative.")
        if stop >= entry:
            raise ValueError("Stop must be below the entry.")
        return self


class PaperPositionResponse(BaseModel):
    id: UUID
    symbol: ProductId
    entry: str
    stop: str
    shares: int
    notional: str
    planned_risk: str
    binding_constraint: Literal["risk", "allocation", "both", "none"]
    exchange_time: str
    recorded_at: str
    execution_permitted: Literal[False] = False
    order_submitted: Literal[False] = False


class PaperPositionListResponse(BaseModel):
    positions: list[PaperPositionResponse]


class ResearchNoteCreate(BaseModel):
    """A private note. This body does not size a position or place an order."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=4000)

    @field_validator("title", "body", mode="before")
    @classmethod
    def strip_required_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class ResearchNoteResponse(BaseModel):
    id: UUID
    title: str
    body: str
    created_at: str


class ResearchNoteListResponse(BaseModel):
    notes: list[ResearchNoteResponse]


class SourceEventCreate(BaseModel):
    """A typed source event. This body does not size a position or place an order."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=120)
    source: str = Field(min_length=1, max_length=200)
    event_time: datetime
    first_public_at: datetime

    @field_validator("title", "source", mode="before")
    @classmethod
    def strip_required_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("event_time", "first_public_at")
    @classmethod
    def timestamp_is_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Timestamp must include a timezone.")
        return value


class SourceEventResponse(BaseModel):
    id: UUID
    title: str
    source: str
    event_time: str
    first_public_at: str
    recorded_at: str
    execution_permitted: Literal[False] = False
    order_submitted: Literal[False] = False


class SourceEventListResponse(BaseModel):
    events: list[SourceEventResponse]


class PaperSizeJournalEntry(BaseModel):
    """A stored paper size. This is not an order."""

    id: UUID
    recorded_at: str
    symbol: ProductId
    equity: str
    entry: str
    stop: str
    shares: int
    planned_risk: str
    binding_constraint: Literal["risk", "allocation", "both", "none"]
    execution_permitted: Literal[False] = False
    order_submitted: Literal[False] = False


class PaperSizeJournalListResponse(BaseModel):
    entries: list[PaperSizeJournalEntry]


class Mac01StatusResponse(BaseModel):
    strategy: Literal["mac-01"]
    strategy_version: str | None
    symbol: Literal["AAPL"]
    broker: Literal["alpaca_trading_api"]
    order_route: Literal["none"]
    order_submitter: Literal["cli_runner_only"]
    config_valid: bool
    config_mode: Literal["paper", "live"] | None
    money: Literal["paper", "real", "unknown"]
    config_live_enabled: bool | None
    config_expected_account_set: bool | None
    config_submit_orders: bool | None
    config_kill_switch: bool | None
    max_notional_per_trade: str | None
    max_position_notional: str | None
    max_orders_per_day: int | None
    last_mode: Literal["paper", "live"] | None
    paused: bool
    kill_switch: bool
    last_run_at: str | None
    last_run_status: str | None
    last_run_message: str | None
    last_session_date: str | None
    disclaimer: str


class Mac01SignalEntry(BaseModel):
    session_date: str
    strategy_version: str
    symbol: str
    side: Literal["BUY", "SELL", "HOLD"]
    reason: str
    close: str
    fast_prev: str
    slow_prev: str
    fast_cur: str
    slow_cur: str
    decision: str
    decision_reason: str
    inputs_hash: str
    created_at: str
    decided_at: str


class Mac01SignalListResponse(BaseModel):
    signals: list[Mac01SignalEntry]


class Mac01OrderEntry(BaseModel):
    client_order_id: str
    mode: Literal["paper", "live"]
    session_date: str
    side: Literal["buy", "sell"]
    notional: str | None
    qty: str | None
    order_type: Literal["market"]
    time_in_force: Literal["day"]
    status: str
    broker_order_id: str | None
    filled_qty: str
    filled_avg_price: str | None
    submitted_at: str | None
    created_at: str
    updated_at: str
    last_error: str | None


class Mac01OrderListResponse(BaseModel):
    orders: list[Mac01OrderEntry]


class Mac01PerformanceResponse(BaseModel):
    mode: Literal["paper", "live"]
    realised_pl: str | None
    realised_available: bool
    unrealised_pl: str | None
    unrealised_available: bool
    position_qty: str | None
    avg_entry_price: str | None
    market_price: str | None
    position_as_of: str | None
    filled_orders: int
    note: str


class Mac01ChartPoint(BaseModel):
    session_date: str
    close: str
    sma_fast: str | None
    sma_slow: str | None


class Mac01ChartMarker(BaseModel):
    session_date: str
    side: Literal["BUY", "SELL"]


class Mac01ChartResponse(BaseModel):
    available: bool
    symbol: Literal["AAPL"]
    source: str | None
    as_of: str | None
    fast_period: int | None
    slow_period: int | None
    points: list[Mac01ChartPoint]
    markers: list[Mac01ChartMarker]
    note: str


class PaperSwapBalance(BaseModel):
    symbol: str
    amount: str


class PaperSwapNetwork(BaseModel):
    chain: Literal["solana", "ethereum", "base"]
    network: Literal["solana-devnet", "sepolia", "base-sepolia"]
    chain_id: Literal["devnet", "11155111", "84532"]
    simulated: Literal[True] = True
    balances: list[PaperSwapBalance]


class PaperSwapPortfolioResponse(BaseModel):
    simulated: Literal[True] = True
    execution_permitted: Literal[False] = False
    order_submitted: Literal[False] = False
    networks: list[PaperSwapNetwork]


class PaperSwapOrderEntry(BaseModel):
    id: UUID
    chain: Literal["solana", "ethereum", "base"]
    network: Literal["solana-devnet", "sepolia", "base-sepolia"]
    chain_id: Literal["devnet", "11155111", "84532"]
    token_in: str
    token_out: str
    amount_in: str
    quoted_out: str
    amount_out: str
    quoted_price: str
    quote_source: str
    price_kind: Literal["pool", "reference"]
    slippage_bps: int
    slippage_applied: str
    fee_estimate: str
    fee_symbol: str
    balances_after: dict[str, str]
    status: Literal["simulated"]
    simulated: Literal[True] = True
    created_at: str
    execution_permitted: Literal[False] = False
    order_submitted: Literal[False] = False


class PaperSwapOrderListResponse(BaseModel):
    simulated: Literal[True] = True
    execution_permitted: Literal[False] = False
    order_submitted: Literal[False] = False
    orders: list[PaperSwapOrderEntry]


AGENT_CODES = (
    "SUPERVISOR-01",
    "DAY-01",
    "STOCK-01",
    "CRYPTO-01",
    "DEFI-01",
    "ETF-01",
    "RESEARCH-01",
    "RISK-01",
    "TREASURY-01",
)

AgentCode = Literal[
    "SUPERVISOR-01",
    "DAY-01",
    "STOCK-01",
    "CRYPTO-01",
    "DEFI-01",
    "ETF-01",
    "RESEARCH-01",
    "RISK-01",
    "TREASURY-01",
]


class AgentDesk(BaseModel):
    """One registry row. The literals below cannot be flipped by a response."""

    code: AgentCode
    display_name: str = Field(min_length=1, max_length=64)
    desk: str = Field(min_length=1, max_length=32)
    status: Literal["disabled", "paused"]
    paper_only: Literal[True]
    can_submit_orders: Literal[False]
    can_sign: Literal[False]
    can_transfer_funds: Literal[False]
    holds_credentials: Literal[False]
    permission_effect: Literal["deny"]


class AgentListResponse(BaseModel):
    agents: list[AgentDesk]
    source: Literal["local_registry"] = "local_registry"
    trading_rights: Literal["denied"] = "denied"
    execution_permitted: Literal[False] = False
    order_submitted: Literal[False] = False


class SystemStatusResponse(BaseModel):
    status: Literal["ok"]
    service: Literal["veytrix-api"]
    env: Literal["local"]
    trading_mode: Literal["paper"]
    live_broker: Literal["disabled"]
    auth: Literal["not_configured"]
    database: Literal["up"]
    execution_permitted: Literal[False]
    order_submitted: Literal[False]
    order_route: Literal["absent"]
    agents_registered: int = Field(ge=0)
    agents_can_trade: Literal[False]
    sample_data: Literal[True]


class SystemStatusUnavailable(BaseModel):
    status: Literal["unavailable"]
    database: Literal["down"]
    execution_permitted: Literal[False] = False
    order_submitted: Literal[False] = False
    order_route: Literal["absent"] = "absent"


DENIED_TOOLS = (
    "submit_order",
    "cancel_order",
    "sign_transaction",
    "broadcast_transaction",
    "bank_transfer",
    "set_live_mode",
    "release_kill_switch",
)

DeniedToolName = Literal[
    "submit_order",
    "cancel_order",
    "sign_transaction",
    "broadcast_transaction",
    "bank_transfer",
    "set_live_mode",
    "release_kill_switch",
]


class DeniedTool(BaseModel):
    """One registry permission. The effect cannot be anything except deny."""

    model_config = ConfigDict(extra="forbid")

    tool_name: DeniedToolName
    effect: Literal["deny"]


class DeskDetailResponse(BaseModel):
    """One desk and its deny list. There is no field that enables it."""

    model_config = ConfigDict(extra="forbid")

    code: AgentCode
    display_name: str = Field(min_length=1, max_length=64)
    desk: str = Field(min_length=1, max_length=32)
    status: Literal["disabled", "paused"]
    paper_only: Literal[True]
    can_submit_orders: Literal[False]
    can_sign: Literal[False]
    can_transfer_funds: Literal[False]
    holds_credentials: Literal[False]
    permission_effect: Literal["deny"]
    notes: str = Field(min_length=1, max_length=500)
    tools: list[DeniedTool] = Field(min_length=7, max_length=7)
    running: Literal[False] = False
    can_enable: Literal[False] = False
    source: Literal["local_registry"] = "local_registry"
    trading_rights: Literal["denied"] = "denied"
    execution_permitted: Literal[False] = False
    order_submitted: Literal[False] = False

    @model_validator(mode="after")
    def tools_match_the_deny_list(self) -> DeskDetailResponse:
        if [tool.tool_name for tool in self.tools] != list(DENIED_TOOLS):
            raise ValueError("denied tools")
        return self


class AuditLogEntry(BaseModel):
    """One size-audit row. The payload is projected. Raw JSON is not returned."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    created_at: str = Field(min_length=20, max_length=40)
    correlation_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    action: Literal["risk.size.recorded"]
    symbol: ProductId
    shares: int = Field(ge=0)
    binding_constraint: Literal["risk", "allocation", "both", "none"]
    execution_permitted: Literal[False]
    order_submitted: Literal[False]


class AuditLogListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    events: list[AuditLogEntry]
    source: Literal["local_audit_log"] = "local_audit_log"
    execution_permitted: Literal[False] = False
    order_submitted: Literal[False] = False


class TreasuryMonthlySummaryResponse(BaseModel):
    """A local projection. There is no field that approves or submits a transfer."""

    model_config = ConfigDict(extra="forbid")

    period: str = Field(pattern=r"^\d{4}-\d{2}$")
    period_closed: Literal[False]
    realised_profit: str = Field(pattern=r"^-?(?:0|[1-9]\d*)(?:\.\d+)?$")
    costs: str = Field(pattern=r"^(?:0|[1-9]\d*)(?:\.\d+)?$")
    loss_carryforward: str = Field(pattern=r"^-?(?:0|[1-9]\d*)(?:\.\d+)?$")
    eligible_profit: str = Field(pattern=r"^-?(?:0|[1-9]\d*)(?:\.\d+)?$")
    proposed_distribution: str = Field(pattern=r"^(?:0|[1-9]\d*)(?:\.\d+)?$")
    retained: str = Field(pattern=r"^(?:0|[1-9]\d*)(?:\.\d+)?$")
    loss_carryforward_out: str = Field(pattern=r"^-?(?:0|[1-9]\d*)(?:\.\d+)?$")
    distribution_fraction: Literal["0.50"]
    distribution_cap: Literal["2000.00"]
    review_day: Literal[5]
    review_on: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    review_shifted_for_weekend: bool
    fills_counted: int = Field(ge=0)
    fees_included: Literal[False]
    carryforward_stored: Literal[False]
    broker_reconciled: Literal[False]
    settled: Literal[False]
    transfer_status: Literal["not_attempted"]
    approval_route: Literal["absent"]
    execution_permitted: Literal[False]
    order_submitted: Literal[False]
    transfer_submitted: Literal[False]
    source: Literal["local_projection"]
    note: str = Field(min_length=1, max_length=500)


class ReminderDatesResponse(BaseModel):
    """Local dates only. There is no field that creates a meeting or a payout."""

    model_config = ConfigDict(extra="forbid")

    period: str = Field(pattern=r"^\d{4}-\d{2}$")
    accounting_close_on: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    accounting_close_shifted_for_weekend: bool
    payout_review_on: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    payout_review_shifted_for_weekend: bool
    meeting_time: Literal["unconfirmed"]
    daypilot: Literal["absent"]
    event_created: Literal[False]
    transfer_submitted: Literal[False]
    execution_permitted: Literal[False]
    order_submitted: Literal[False]
    source: Literal["local_calendar"]
    note: str = Field(min_length=1, max_length=400)


class ToolSpecResponse(BaseModel):
    """One catalogue row. The route cannot mark it as executing."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=r"^[a-z][a-z0-9_]{1,64}$")
    effect: Literal["read", "deny"]
    executes: Literal[False]


class ToolCatalogueResponse(BaseModel):
    """The local supervisor catalogue. Chat is absent and nothing executes."""

    model_config = ConfigDict(extra="forbid")

    source: Literal["local_catalogue"]
    model: Literal["not_configured"]
    chat: Literal["absent"]
    tools: list[ToolSpecResponse] = Field(min_length=1, max_length=32)
    executed: Literal[False]
    invokes_model: Literal[False]
    execution_permitted: Literal[False]
    order_submitted: Literal[False]
    note: str = Field(min_length=1, max_length=400)

    @model_validator(mode="after")
    def names_are_unique(self) -> ToolCatalogueResponse:
        names = [tool.name for tool in self.tools]
        if len(names) != len(set(names)):
            raise ValueError("Tool names must be unique.")
        if "submit_order" not in names or "size_position" not in names:
            raise ValueError("The deny list is incomplete.")
        return self


class ToolCheckRequest(BaseModel):
    """A hypothetical tool call. This body cannot run the tool."""

    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    arguments: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def arguments_stay_small(self) -> ToolCheckRequest:
        if len(self.arguments) > 4:
            raise ValueError("arguments has too many fields.")
        for key, item in self.arguments.items():
            if re.fullmatch(r"^[a-z][a-z0-9_]{0,31}$", key) is None:
                raise ValueError("argument name is not allowed.")
            if len(item) > 80:
                raise ValueError("argument value is too long.")
        return self


class SubmissionCondition(BaseModel):
    """One live-gate condition. A true `met` still cannot submit from this API."""

    model_config = ConfigDict(extra="forbid")

    name: Literal[
        "mode_live",
        "live_enabled",
        "submit_orders",
        "confirm_phrase",
        "submit_flag",
        "account_match",
        "account_active",
        "kill_switch_off",
    ]
    met: bool


class SubmissionEvidenceResponse(BaseModel):
    """The eight live-gate conditions, plus the fact that this process cannot submit."""

    model_config = ConfigDict(extra="forbid")

    config_valid: bool
    config_mode: Literal["paper", "live"] | None
    config_live_enabled: bool | None
    config_submit_orders: bool | None
    config_kill_switch: bool | None
    expected_account_set: bool | None
    conditions: list[SubmissionCondition] = Field(min_length=8, max_length=8)
    conditions_met: int = Field(ge=0, le=8)
    account_status: Literal["not_read"]
    ledger_kill_switch: Literal["not_read"]
    submit_flag: Literal[False]
    api_reaches_engine: Literal[False]
    broker_called: Literal[False]
    paper_submission_from_api: Literal[False]
    live_submission_possible: Literal[False]
    expected_account_echoed: Literal[False]
    confirm_phrase_echoed: Literal[False]
    execution_permitted: Literal[False]
    order_submitted: Literal[False]
    order_route: Literal["absent"]
    source: Literal["local_config"]
    note: str = Field(min_length=1, max_length=400)

    @model_validator(mode="after")
    def conditions_stay_in_order(self) -> SubmissionEvidenceResponse:
        names = [item.name for item in self.conditions]
        expected = [
            "mode_live",
            "live_enabled",
            "submit_orders",
            "confirm_phrase",
            "submit_flag",
            "account_match",
            "account_active",
            "kill_switch_off",
        ]
        if names != expected:
            raise ValueError("Live-gate conditions are incomplete.")
        if self.conditions_met != sum(item.met for item in self.conditions):
            raise ValueError("conditions_met does not match the list.")
        if any(
            item.met
            for item in self.conditions
            if item.name in ("submit_flag", "account_match", "account_active", "kill_switch_off")
        ):
            raise ValueError("This API cannot meet the broker or submit conditions.")
        return self


class ReconciliationRow(BaseModel):
    """One local order beside an unread broker. `matched` cannot become true."""

    model_config = ConfigDict(extra="forbid")

    client_order_id: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,128}$")
    mode: Literal["paper", "live"]
    side: Literal["buy", "sell"]
    local_status: Literal[
        "pending_submit",
        "pending_new",
        "pending_cancel",
        "pending_replace",
        "new",
        "accepted",
        "accepted_for_bidding",
        "partially_filled",
        "filled",
        "done_for_day",
        "canceled",
        "expired",
        "replaced",
        "rejected",
        "not_found",
        "held",
        "stopped",
        "suspended",
        "calculated",
    ]
    broker_order_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9-]{1,64}$")
    broker_order_stored: bool
    broker_status: Literal["not_read"]
    matched: Literal[False]
    reason: Literal["broker_not_read"]


LOCAL_ORDER_STATUSES = frozenset(
    {
        "pending_submit",
        "pending_new",
        "pending_cancel",
        "pending_replace",
        "new",
        "accepted",
        "accepted_for_bidding",
        "partially_filled",
        "filled",
        "done_for_day",
        "canceled",
        "expired",
        "replaced",
        "rejected",
        "not_found",
        "held",
        "stopped",
        "suspended",
        "calculated",
    }
)
TERMINAL_ORDER_STATUSES = frozenset(
    {"filled", "canceled", "expired", "rejected", "replaced", "not_found"}
)


class ReconciliationResponse(BaseModel):
    """A local ledger read. There is no field that marks the book reconciled."""

    model_config = ConfigDict(extra="forbid")

    local_orders: int = Field(ge=0)
    local_fills: int = Field(ge=0)
    local_open: int = Field(ge=0)
    broker_rows_read: Literal[0]
    broker_read: Literal["absent"]
    alpaca_called: Literal[False]
    reconciled: Literal[False]
    rows: list[ReconciliationRow] = Field(max_length=100)
    execution_permitted: Literal[False]
    order_submitted: Literal[False]
    order_route: Literal["absent"]
    source: Literal["local_ledger"]
    note: str = Field(min_length=1, max_length=400)

    @model_validator(mode="after")
    def counts_match_the_rows(self) -> ReconciliationResponse:
        if self.local_orders != len(self.rows):
            raise ValueError("local_orders does not match the rows.")
        if self.local_fills > self.local_orders or self.local_open > self.local_orders:
            raise ValueError("fill or open count exceeds the rows.")
        if any(row.matched or row.broker_status != "not_read" for row in self.rows):
            raise ValueError("A row cannot claim a broker match.")
        return self


class Mac01ScheduleResponse(BaseModel):
    """The published MAC-01 clock. This process does not start it or read a calendar."""

    model_config = ConfigDict(extra="forbid")

    strategy: Literal["mac-01"]
    timezone: Literal["America/New_York"]
    run_clock: Literal["09:35"]
    delay_after_open_minutes: Literal[5]
    calendar: Literal["not_read"]
    next_session: Literal["unknown"]
    running: Literal[False]
    process: Literal["absent"]
    submit_flag: Literal[False]
    can_start: Literal[False]
    config_valid: bool
    config_mode: Literal["paper", "live"] | None
    config_submit_orders: bool | None
    config_live_enabled: bool | None
    alpaca_called: Literal[False]
    execution_permitted: Literal[False]
    order_submitted: Literal[False]
    order_route: Literal["absent"]
    source: Literal["local_config"]
    note: str = Field(min_length=1, max_length=400)


class ToolCheckResponse(BaseModel):
    """The local decision. `executed` stays false even when the decision is accept."""

    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    decision: Literal["accept", "deny"]
    reasons: list[str] = Field(max_length=3)
    effect: Literal["read", "deny", "unknown"]
    executed: Literal[False]
    invokes_model: Literal[False]
    execution_permitted: Literal[False]
    order_submitted: Literal[False]
    note: str = Field(min_length=1, max_length=400)

    @model_validator(mode="after")
    def reasons_match_decision(self) -> ToolCheckResponse:
        known = ("injection", "tool", "schema")
        if any(reason not in known for reason in self.reasons):
            raise ValueError("Unknown tool reason.")
        ordered = [reason for reason in known if reason in self.reasons]
        if self.reasons != ordered:
            raise ValueError("Tool reasons are out of order.")
        if self.decision == "accept" and (self.reasons or self.effect != "read"):
            raise ValueError("An accepted check is a read with no reasons.")
        if self.decision == "deny" and not self.reasons:
            raise ValueError("A denied check names a reason.")
        return self
