"""Text safety for the communication layer.

Nothing in `veytrix_api.comms` can place an order, call MAC-01, or run the swap
CLI. These helpers keep outside text (research notes, source events) from being
read as an instruction, and they classify trade-like chat so a desk can say no.
"""

from __future__ import annotations

import re

# The fifth feature flag is not a setting. It is a constant, and the tests pin it.
LIVE_EXECUTION_ENABLED = False

_ORDER_INTENT = re.compile(
    r"\b(buy|sell|place|submit|execute)\b"
    r".{0,40}\b(order|orders|trade|trades|shares?|position|stock|crypto|swap|btc|eth|sol|aapl|etf)\b"
    r"|\b(withdraw|payout|wire|bank transfer|transfer (the )?funds?|move (the )?funds?)\b"
    r"|\b(go live|enable live|live mode|live trading|release the kill switch|unpause)\b"
    r"|\b(sign|broadcast)\b.{0,20}\b(transaction|tx|swap)\b",
    re.IGNORECASE | re.DOTALL,
)

_INJECTION = re.compile(
    r"ignore (all |any )?(previous|prior|above)|disregard|system prompt|developer message"
    r"|you (must|should|are now)|act as|override|jailbreak|new instructions?"
    r"|\b(buy|sell|place|submit|execute)\b.{0,30}\b(order|shares?)\b|api[_ -]?key|private key",
    re.IGNORECASE | re.DOTALL,
)

WITHHELD = "[withheld: instruction-like text]"


def wants_order(text: str) -> bool:
    """True when chat text asks for something this build cannot and will not do."""

    return _ORDER_INTENT.search(text) is not None


def looks_like_instruction(text: str) -> bool:
    return _INJECTION.search(text) is not None


def clean(text: str, limit: int) -> str:
    """Strip control characters, collapse blanks, and cut to `limit` characters."""

    flat = " ".join("".join(ch if ch >= " " else " " for ch in text).split())
    if len(flat) <= limit:
        return flat
    return flat[: max(0, limit - 1)].rstrip() + "…"


def quote_external(text: str, limit: int = 80) -> str:
    """Return outside text as quoted data. Instruction-like text is withheld, not repeated."""

    if looks_like_instruction(text):
        return WITHHELD
    return f"“{clean(text, limit).replace('“', '"').replace('”', '"')}”"


def normalise(text: str) -> str:
    """Stable form used for loop detection."""

    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
