"""Paper validator for the TradersPost webhook JSON body.

TradersPost documents POST JSON to a strategy webhook URL. Required fields are
`ticker` and `action`. This module checks that shape and returns a rejection.
It does not call TradersPost and it does not call a broker.
"""

from __future__ import annotations

import json

from veytrix_execution.audit import Validation, redact
from veytrix_execution.payload import encode, media_type, non_negative, over_budget

ACTIONS = frozenset({"buy", "sell", "add", "resize", "exit", "reverse", "breakeven", "cancel"})
ORDER_TYPES = frozenset({"market", "limit", "stop", "stop_limit", "trailing_stop"})
SENTIMENTS = frozenset({"bullish", "bearish", "flat", "long", "short"})


def _fail(code: str, message: str, *, store: bool = True) -> Validation:
    return Validation(False, code, message, {}, store)


def _parse(payload: object, content_type: str | None) -> tuple[object | None, Validation | None]:
    declared = media_type(content_type)
    if isinstance(payload, bytes | str):
        if declared not in {None, "application/json"}:
            return None, _fail("malformed-json", "TradersPost documents a JSON body.")
        if isinstance(payload, bytes):
            try:
                text = payload.decode("utf-8")
            except UnicodeDecodeError:
                return None, _fail("malformed-json", "Body is not UTF-8 JSON.")
        else:
            text = payload
        encoded = text.encode("utf-8")
        try:
            parsed: object = json.loads(text) if text.strip() else {}
        except ValueError:
            if len(encoded) > 16_384:
                return None, _fail(
                    "payload-budget-exceeded",
                    "Body exceeds 16384 bytes.",
                    store=False,
                )
            return None, _fail("malformed-json", "Body is not valid JSON.")
    else:
        parsed = payload
        encoded = encode(parsed)
        if encoded is None:
            return None, _fail("malformed-json", "Body is not JSON-compatible.")
    if encoded is None:
        return None, _fail("malformed-json", "Body is not JSON-compatible.")
    reason = over_budget(encoded, parsed)
    if reason is not None:
        return None, _fail("payload-budget-exceeded", reason, store=False)
    return parsed, None


def validate_traderspost(payload: object, content_type: str | None = None) -> Validation:
    parsed, error = _parse(payload, content_type)
    if error is not None:
        return error
    if isinstance(parsed, list):
        return _fail(
            "batch-signals-not-enabled",
            "Batch signals are off. No item is treated as an order.",
        )
    if parsed == {}:
        return _fail("empty-json", "The JSON object is empty.")
    if not isinstance(parsed, dict):
        return _fail("invalid-payload", "Both the action and ticker fields are required.")

    ticker = parsed.get("ticker")
    action = parsed.get("action")
    if not isinstance(ticker, str) or not ticker.strip() or ticker.startswith("="):
        return _fail("invalid-payload", "Both the action and ticker fields are required.")
    if len(ticker) > 64:
        return _fail("invalid-payload", "Ticker is longer than 64 characters.")
    if not isinstance(action, str):
        return _fail("invalid-payload", "Both the action and ticker fields are required.")
    if action not in ACTIONS:
        return _fail("invalid-action", "Action is not one of the documented TradersPost values.")
    if action == "resize" and "quantity" not in parsed:
        return _fail("resize-requires-quantity", "Resize requires quantity.")
    if "quantity" in parsed and not non_negative(parsed["quantity"]):
        return _fail("invalid-quantity", "Quantity is not a non-negative number.")
    if "orderType" in parsed and parsed["orderType"] not in ORDER_TYPES:
        return _fail("invalid-order-type", "orderType is not a documented value.")
    if "sentiment" in parsed and parsed["sentiment"] not in SENTIMENTS:
        return _fail("invalid-sentiment", "sentiment is not a documented value.")
    if "test" in parsed and not isinstance(parsed["test"], bool):
        return _fail("invalid-payload", "test must be a boolean when it is present.")

    sender = redact(parsed)
    signal: dict[str, object] = {
        "provider": "traderspost",
        "sender": sender if isinstance(sender, dict) else {},
        "formula_evaluated": False,
        "sender_marked_test": parsed.get("test") is True,
    }
    return Validation(
        True,
        "broker-forwarding-disabled",
        "Payload matches the documented fields.",
        signal,
    )
