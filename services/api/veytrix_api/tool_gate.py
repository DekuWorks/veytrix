"""Local supervisor tool check.

The catalogue names read-only tools and denied tools. `check_tool_call`
returns a decision. It does not run the tool, call a model, or submit an
order. A second call with the same inputs returns the same decision.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from veytrix_api.schemas import AGENT_CODES, DENIED_TOOLS

READ_TOOLS = (
    "read_system_status",
    "read_agents",
    "read_desk",
    "read_market_health",
    "read_treasury_summary",
    "read_audit_log",
    "read_research_notes",
)
EXTRA_DENY = (
    "enable_agent",
    "approve_payout",
    "size_position",
    "supervisor_chat",
)
DENY_TOOLS = DENIED_TOOLS + EXTRA_DENY
_READ_ARGUMENTS = {
    "read_system_status": frozenset(),
    "read_agents": frozenset(),
    "read_desk": frozenset({"code"}),
    "read_market_health": frozenset(),
    "read_treasury_summary": frozenset(),
    "read_audit_log": frozenset(),
    "read_research_notes": frozenset(),
}
_REASON_ORDER = ("injection", "tool", "schema")
_TOOL_NAME = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_ARG_NAME = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_NEEDLES = (
    "ignore previous",
    "ignore all",
    "execution_permitted",
    "order_submitted",
    "system prompt",
    "you are now",
)


class ToolInputError(ValueError):
    """The check inputs are not a plain tool name and string arguments."""


@dataclass(frozen=True)
class ToolSpec:
    """One catalogue row. `executes` cannot become true from here."""

    name: str
    effect: Literal["read", "deny"]
    executes: Literal[False] = False


@dataclass(frozen=True)
class ToolDecision:
    """A hypothetical check. `executed` stays false."""

    tool_name: str
    decision: Literal["accept", "deny"]
    reasons: tuple[str, ...]
    effect: Literal["read", "deny", "unknown"]
    executed: Literal[False] = False
    invokes_model: Literal[False] = False
    execution_permitted: Literal[False] = False
    order_submitted: Literal[False] = False


def catalogue() -> tuple[ToolSpec, ...]:
    """Read tools first, then every denied name. None of them execute."""

    reads = tuple(ToolSpec(name=name, effect="read") for name in READ_TOOLS)
    denies = tuple(ToolSpec(name=name, effect="deny") for name in DENY_TOOLS)
    return reads + denies


def _arguments(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ToolInputError("arguments must be an object of strings.")
    if len(value) > 4:
        raise ToolInputError("arguments has too many fields.")
    cleaned: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or _ARG_NAME.fullmatch(key) is None:
            raise ToolInputError("argument name is not allowed.")
        if isinstance(item, bool) or not isinstance(item, str):
            raise ToolInputError("argument values must be strings.")
        if len(item) > 80:
            raise ToolInputError("argument value is too long.")
        cleaned[key] = item
    return cleaned


def _injects(text: str) -> bool:
    folded = text.casefold()
    return any(needle in folded for needle in _NEEDLES)


def check_tool_call(*, tool_name: str, arguments: object) -> ToolDecision:
    """Decide whether a named call matches the local catalogue.

    An allowlisted read with the expected string arguments is `accept`.
    Accepting does not run the tool. A denied name, an unknown name, a
    schema mismatch, or an instruction hidden in an argument is `deny`.
    """

    if not isinstance(tool_name, str) or _TOOL_NAME.fullmatch(tool_name) is None:
        raise ToolInputError("tool_name must be a lowercase tool name.")
    cleaned = _arguments(arguments)
    if tool_name in READ_TOOLS:
        effect: Literal["read", "deny", "unknown"] = "read"
    elif tool_name in DENY_TOOLS:
        effect = "deny"
    else:
        effect = "unknown"
    reasons: list[str] = []
    if _injects(tool_name) or any(_injects(item) for item in cleaned.values()):
        reasons.append("injection")
    if effect != "read":
        reasons.append("tool")
    else:
        expected = _READ_ARGUMENTS[tool_name]
        if set(cleaned) != expected:
            reasons.append("schema")
        elif tool_name == "read_desk" and cleaned["code"] not in AGENT_CODES:
            reasons.append("schema")
    ordered = tuple(reason for reason in _REASON_ORDER if reason in reasons)
    return ToolDecision(
        tool_name=tool_name,
        decision="deny" if ordered else "accept",
        reasons=ordered,
        effect=effect,
    )
