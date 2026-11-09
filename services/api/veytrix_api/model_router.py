"""Choose a model for a desk without calling one.

Desk names stay independent of providers. Paid providers are refused unless
the process is explicitly allowed to spend and the monthly ceiling is above
zero. This module never purchases credit and never opens a network connection.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

PERSONAS: dict[str, str] = {
    "SUPERVISOR-01": "Roads",
    "DAY-01": "Dayvid",
    "STOCK-01": "Vex",
    "CRYPTO-01": "Nyx",
    "DEFI-01": "Cipher",
    "ETF-01": "Lyra",
    "RESEARCH-01": "Astra",
    "RISK-01": "Aegis",
    "TREASURY-01": "Midas",
}

DETERMINISTIC_TASKS = frozenset(
    {
        "position_size",
        "sma_crossover",
        "treasury_split",
        "reconcile",
        "risk_check",
    }
)

PAID_PROVIDERS = frozenset({"openai", "anthropic", "google", "cursor", "grok"})
LOCAL_PROVIDERS = frozenset({"none", "ollama"})


@dataclass(frozen=True)
class RouteDecision:
    agent_code: str
    persona: str
    task: str
    provider: str
    allowed: bool
    reason: str
    estimated_usd: Decimal
    paid: bool
    execution_permitted: bool = False
    order_submitted: bool = False


def route_task(
    *,
    agent_code: str,
    task: str,
    provider: str,
    paid_inference_enabled: bool,
    monthly_ceiling_usd: Decimal,
    spent_usd: Decimal,
    ollama_configured: bool,
) -> RouteDecision:
    persona = PERSONAS.get(agent_code, "")
    if not persona:
        return RouteDecision(
            agent_code=agent_code,
            persona="",
            task=task,
            provider="none",
            allowed=False,
            reason="unknown_desk",
            estimated_usd=Decimal("0"),
            paid=False,
        )
    if task in DETERMINISTIC_TASKS:
        return RouteDecision(
            agent_code=agent_code,
            persona=persona,
            task=task,
            provider="none",
            allowed=True,
            reason="deterministic",
            estimated_usd=Decimal("0"),
            paid=False,
        )
    if provider in PAID_PROVIDERS or provider == "cursor":
        remaining = monthly_ceiling_usd - spent_usd
        if not paid_inference_enabled or monthly_ceiling_usd <= 0 or remaining <= 0:
            return RouteDecision(
                agent_code=agent_code,
                persona=persona,
                task=task,
                provider=provider,
                allowed=False,
                reason="paid_inference_paused",
                estimated_usd=Decimal("0"),
                paid=True,
            )
        return RouteDecision(
            agent_code=agent_code,
            persona=persona,
            task=task,
            provider=provider,
            allowed=False,
            reason="paid_provider_not_configured",
            estimated_usd=Decimal("0"),
            paid=True,
        )
    if provider == "ollama":
        if not ollama_configured:
            return RouteDecision(
                agent_code=agent_code,
                persona=persona,
                task=task,
                provider="ollama",
                allowed=False,
                reason="ollama_not_configured",
                estimated_usd=Decimal("0"),
                paid=False,
            )
        return RouteDecision(
            agent_code=agent_code,
            persona=persona,
            task=task,
            provider="ollama",
            allowed=True,
            reason="local_model",
            estimated_usd=Decimal("0"),
            paid=False,
        )
    return RouteDecision(
        agent_code=agent_code,
        persona=persona,
        task=task,
        provider="none",
        allowed=False,
        reason="no_provider",
        estimated_usd=Decimal("0"),
        paid=False,
    )
