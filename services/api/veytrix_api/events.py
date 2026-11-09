"""Local shapes for later event publishing.

Nothing in this module is mounted on the API, written to a queue, or able to
submit an order. SQS remains blocked. A distribution proposal cannot say that
a transfer happened, and an order shape cannot say that this API submitted it
or that the order was live.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EVENT_TYPES = (
    "MarketBarClosed",
    "StrategySignalCreated",
    "TradeIntentProposed",
    "RiskDecisionMade",
    "OrderSubmitted",
    "BrokerOrderUpdated",
    "FillReconciled",
    "AgentRunCompleted",
    "IncidentRaised",
    "AccountingPeriodClosed",
    "DistributionProposed",
)


class EventContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    occurred_at: datetime
    correlation_id: str = Field(min_length=1, max_length=64)


class MarketBarClosed(EventContract):
    event_type: Literal["MarketBarClosed"] = "MarketBarClosed"
    symbol: str = Field(min_length=1, max_length=32)
    interval: Literal["1d", "1m"]
    bar_start: datetime
    source: Literal["sample", "coinbase", "broker"]


class StrategySignalCreated(EventContract):
    event_type: Literal["StrategySignalCreated"] = "StrategySignalCreated"
    strategy: Literal["mac-01"]
    symbol: Literal["AAPL"]
    direction: Literal["bullish", "bearish", "none"]
    order_submitted: Literal[False] = False


class TradeIntentProposed(EventContract):
    event_type: Literal["TradeIntentProposed"] = "TradeIntentProposed"
    strategy: Literal["mac-01"]
    symbol: Literal["AAPL"]
    side: Literal["buy", "sell"]
    execution_permitted: Literal[False] = False
    order_submitted: Literal[False] = False


class RiskDecisionMade(EventContract):
    event_type: Literal["RiskDecisionMade"] = "RiskDecisionMade"
    decision: Literal["deny"]
    reason: str = Field(min_length=1, max_length=200)
    execution_permitted: Literal[False] = False


class OrderSubmitted(EventContract):
    """A record shape only. This API has no route that constructs it."""

    event_type: Literal["OrderSubmitted"] = "OrderSubmitted"
    submitted_by: Literal["cli_runner_only"]
    live: Literal[False] = False
    broker: Literal["alpaca_paper"]
    symbol: Literal["AAPL"]
    side: Literal["buy", "sell"]
    client_order_id: str = Field(min_length=1, max_length=128)


class BrokerOrderUpdated(EventContract):
    event_type: Literal["BrokerOrderUpdated"] = "BrokerOrderUpdated"
    broker: Literal["alpaca_paper"]
    live: Literal[False] = False
    client_order_id: str = Field(min_length=1, max_length=128)
    broker_status: Literal[
        "accepted",
        "pending",
        "partially_filled",
        "filled",
        "canceled",
        "expired",
        "rejected",
    ]


class FillReconciled(EventContract):
    event_type: Literal["FillReconciled"] = "FillReconciled"
    broker: Literal["alpaca_paper"]
    live: Literal[False] = False
    client_order_id: str = Field(min_length=1, max_length=128)
    simulated: Literal[False] = False


class AgentRunCompleted(EventContract):
    event_type: Literal["AgentRunCompleted"] = "AgentRunCompleted"
    agent_code: Literal[
        "SUPERVISOR-01",
        "DAY-01",
        "STOCK-01",
        "CRYPTO-01",
        "DEFI-01",
        "ETF-01",
        "FUTURES-01",
        "RESEARCH-01",
        "RISK-01",
        "TREASURY-01",
    ]
    run_status: Literal["recorded", "failed", "skipped"]
    can_submit_orders: Literal[False] = False
    can_sign: Literal[False] = False
    can_transfer_funds: Literal[False] = False


class IncidentRaised(EventContract):
    event_type: Literal["IncidentRaised"] = "IncidentRaised"
    severity: Literal["info", "warning", "stop"]
    summary: str = Field(min_length=1, max_length=500)


class AccountingPeriodClosed(EventContract):
    event_type: Literal["AccountingPeriodClosed"] = "AccountingPeriodClosed"
    period: str = Field(pattern=r"^\d{4}-\d{2}$")
    payout_executed: Literal[False] = False


class DistributionProposed(EventContract):
    event_type: Literal["DistributionProposed"] = "DistributionProposed"
    amount: str = Field(min_length=1, max_length=32)
    currency: Literal["USD"]
    transfer_executed: Literal[False] = False


CONTRACTS = {
    "MarketBarClosed": MarketBarClosed,
    "StrategySignalCreated": StrategySignalCreated,
    "TradeIntentProposed": TradeIntentProposed,
    "RiskDecisionMade": RiskDecisionMade,
    "OrderSubmitted": OrderSubmitted,
    "BrokerOrderUpdated": BrokerOrderUpdated,
    "FillReconciled": FillReconciled,
    "AgentRunCompleted": AgentRunCompleted,
    "IncidentRaised": IncidentRaised,
    "AccountingPeriodClosed": AccountingPeriodClosed,
    "DistributionProposed": DistributionProposed,
}
