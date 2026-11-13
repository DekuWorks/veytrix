"""Everyday Grok assistant. No brokerage tools and no Veytrix trading tables.

The xAI key stays with the caller. This module never reads a key from disk and
never places a network call. A missing key is an unconfigured state.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class TenantStore:
    """Per-tenant notes. One tenant cannot read another tenant's text."""

    _notes: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))

    def add(self, tenant: str, text: str) -> None:
        self._notes[tenant].append(text)

    def read(self, tenant: str) -> list[str]:
        return list(self._notes.get(tenant, []))


@dataclass
class RateLimit:
    limit: int = 3
    _counts: dict[str, int] = field(default_factory=dict)

    def allow(self, tenant: str) -> bool:
        used = self._counts.get(tenant, 0)
        if used >= self.limit:
            return False
        self._counts[tenant] = used + 1
        return True


def reply(
    tenant: str,
    prompt: str,
    *,
    key_present: bool,
    store: TenantStore,
    limiter: RateLimit,
) -> dict[str, str | bool]:
    """Return a local decision. This function does not call xAI."""

    if not key_present:
        return {"origin": "unconfigured", "text": "Grok is not configured.", "network": False}
    if not limiter.allow(tenant):
        return {"origin": "rate_limited", "text": "Too many requests.", "network": False}
    store.add(tenant, prompt)
    return {
        "origin": "not_sent",
        "text": "The prompt stayed on this machine. No model call was made.",
        "network": False,
    }
