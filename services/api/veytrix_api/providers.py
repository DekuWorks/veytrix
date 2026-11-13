"""Provider seams for development and paper. No network calls.

Development uses deterministic stand-ins. Paper reports the real providers as
disconnected until a connectivity test exists. Live mode never reaches this
module, because boot refuses it. Nothing here imports a broker, a model SDK,
MAC-01, or the paper-swap CLI.
"""

from __future__ import annotations

import hashlib
import os
from typing import Literal, Protocol

from pydantic import BaseModel

from veytrix_api.settings import Settings

DataState = Literal["simulated", "disconnected", "disabled"]
ReplyOrigin = Literal["simulated"]


class ModelReply(BaseModel):
    origin: ReplyOrigin
    provider: Literal["mock"]
    label: Literal["simulated"]
    connected: Literal[False] = False
    text: str


class ModelProvider(Protocol):
    def complete(self, prompt: str) -> ModelReply:
        """Return a labelled reply. Implementations must not open a socket."""


class MarketView(BaseModel):
    state: DataState
    price: None = None
    source: Literal["development_fixture", "not_connected"]


class MarketDataProvider(Protocol):
    def view(self, symbol: str) -> MarketView:
        """Describe a price source. Development does not invent a tradable price."""


class BrokerView(BaseModel):
    simulated: Literal["simulated"]
    paper: Literal["disconnected"]
    live: Literal["disabled"]
    order_submitted: Literal[False] = False
    execution_permitted: Literal[False] = False
    reaches_mac01: Literal[False] = False
    reaches_alpaca: Literal[False] = False
    reaches_swap_signing: Literal[False] = False


class BrokerProvider(Protocol):
    def view(self) -> BrokerView:
        """Report execution channels. This object cannot submit."""


class ModelPosture(BaseModel):
    provider: Literal["mock"]
    preferred_production_provider: Literal["claude"]
    production_state: Literal["disconnected"]
    credential_present: bool
    connectivity: Literal["not_tested"]
    reply_origin: ReplyOrigin
    reply_label: Literal["simulated"]
    connected: Literal[False] = False


class ProviderPosture(BaseModel):
    runtime_mode: Literal["development", "paper"]
    supabase: Literal["not_used", "disconnected"]
    live_execution: Literal[False] = False
    order_route: Literal["absent"]
    model: ModelPosture
    market: MarketView
    broker: BrokerView
    mock_reply: ModelReply


class MockModel:
    """Deterministic stand-in. The origin is simulated, never a model label."""

    def complete(self, prompt: str) -> ModelReply:
        token = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:8]
        return ModelReply(
            origin="simulated",
            provider="mock",
            label="simulated",
            connected=False,
            text=f"Simulated reply {token}. No model was called.",
        )


class SimulatedMarket:
    def view(self, symbol: str) -> MarketView:
        del symbol
        return MarketView(state="simulated", price=None, source="development_fixture")


class DisconnectedMarket:
    def view(self, symbol: str) -> MarketView:
        del symbol
        return MarketView(state="disconnected", price=None, source="not_connected")


class SimulatedBroker:
    """Simulated channel stays available when real paper execution is disconnected."""

    def view(self) -> BrokerView:
        return BrokerView(
            simulated="simulated",
            paper="disconnected",
            live="disabled",
        )


def claude_credential_present() -> bool:
    """True only when the variable is non-empty. The value is not returned or logged."""

    raw = os.environ.get("ANTHROPIC_API_KEY")
    return bool(raw and raw.strip())


def select_model(mode: str) -> ModelProvider:
    """Claude is the preferred production provider and is not constructed.

    A later provider implements `ModelProvider`. Missing or unverified
    credentials stay on the mock. `mode` is accepted so the selector can grow
    without a new call shape; both development and paper use the mock today.
    """

    del mode
    return MockModel()


def select_market(mode: Literal["development", "paper"]) -> MarketDataProvider:
    if mode == "development":
        return SimulatedMarket()
    return DisconnectedMarket()


def select_broker() -> BrokerProvider:
    return SimulatedBroker()


def build_posture(settings: Settings, *, prompt: str = "development") -> ProviderPosture:
    if settings.veytrix_mode == "live":
        raise RuntimeError("Live mode does not build a provider posture.")
    mode: Literal["development", "paper"] = settings.veytrix_mode
    reply = select_model(mode).complete(prompt)
    if reply.origin != "simulated":
        raise RuntimeError("Mock replies must stay simulated.")
    return ProviderPosture(
        runtime_mode=mode,
        supabase="not_used" if mode == "development" else "disconnected",
        live_execution=False,
        order_route="absent",
        model=ModelPosture(
            provider="mock",
            preferred_production_provider="claude",
            production_state="disconnected",
            credential_present=claude_credential_present(),
            connectivity="not_tested",
            reply_origin=reply.origin,
            reply_label="simulated",
            connected=False,
        ),
        market=select_market(mode).view("SAMPLE"),
        broker=select_broker().view(),
        mock_reply=reply,
    )
