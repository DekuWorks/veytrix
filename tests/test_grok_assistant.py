"""Grok assistant isolation. No network and no trading imports."""

from __future__ import annotations

from pathlib import Path

from grok_assistant import RateLimit, TenantStore, reply

SOURCE = Path(__file__).resolve().parents[1] / "apps" / "grok-assistant" / "grok_assistant.py"


def test_tenants_cannot_read_each_other() -> None:
    store = TenantStore()
    limiter = RateLimit(limit=5)
    reply("alpha", "hello from alpha", key_present=True, store=store, limiter=limiter)
    reply("beta", "hello from beta", key_present=True, store=store, limiter=limiter)
    assert store.read("alpha") == ["hello from alpha"]
    assert store.read("beta") == ["hello from beta"]


def test_rate_limit_and_missing_key_do_not_call_out() -> None:
    store = TenantStore()
    limiter = RateLimit(limit=1)
    first = reply("alpha", "one", key_present=True, store=store, limiter=limiter)
    second = reply("alpha", "two", key_present=True, store=store, limiter=limiter)
    missing = reply("alpha", "three", key_present=False, store=store, limiter=RateLimit())
    assert first["network"] is False and first["origin"] == "not_sent"
    assert second["origin"] == "rate_limited"
    assert missing["origin"] == "unconfigured"
    assert store.read("alpha") == ["one"]


def test_source_has_no_trading_imports() -> None:
    text = SOURCE.read_text(encoding="utf-8")
    assert "veytrix_quant" not in text
    assert "alpaca" not in text
    assert "urlopen" not in text
    assert "ANTHROPIC" not in text
