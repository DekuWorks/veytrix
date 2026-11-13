"""Paper validator for the SignalStack Alpaca stock webhook JSON.

The Alpaca stock help page documents `symbol`, `action` (`buy`, `sell`, `close`),
optional `quantity`, `quantity_type`, `limit_price`, and `stop_price`. Omitted
quantity is left empty. This recorder does not substitute 1 and does not send
the payload to SignalStack or to a broker.
"""

from __future__ import annotations

import json
import re

from veytrix_execution.audit import Validation, redact
from veytrix_execution.limits import MAX_BODY_BYTES
from veytrix_execution.payload import encode, media_type, over_budget, positive

ACTIONS = frozenset({"buy", "sell", "close"})
QUANTITY_TYPES = frozenset({"fixed", "cash", "percent_of_equity"})
_SYMBOL = re.compile(r"^[A-Z0-9][A-Z0-9./-]{0,31}$")


def _fail(code: str, message: str, *, store: bool = True) -> Validation:
    return Validation(False, code, message, {}, store)


def validate_signalstack(payload: object, content_type: str | None = None) -> Validation:
    declared = media_type(content_type)
    if isinstance(payload, bytes | str):
        if declared not in {None, "application/json"}:
            return _fail("malformed-json", "SignalStack's Alpaca examples are JSON objects.")
        if isinstance(payload, bytes):
            try:
                text = payload.decode("utf-8")
            except UnicodeDecodeError:
                return _fail("malformed-json", "Body is not UTF-8 JSON.")
        else:
            text = payload
        if len(text.encode("utf-8")) > MAX_BODY_BYTES:
            return _fail("payload-budget-exceeded", "Body exceeds 16384 bytes.", store=False)
        try:
            parsed: object = json.loads(text) if text.strip() else {}
        except ValueError:
            return _fail("malformed-json", "Body is not valid JSON.")
    else:
        parsed = payload
    encoded = encode(parsed)
    if encoded is None:
        return _fail("malformed-json", "Body is not JSON-compatible.")
    reason = over_budget(encoded, parsed)
    if reason is not None:
        return _fail("payload-budget-exceeded", reason, store=False)
    if not isinstance(parsed, dict) or not parsed:
        return _fail("invalid-payload", "symbol and action are required.")

    symbol = parsed.get("symbol")
    action = parsed.get("action")
    if not isinstance(symbol, str) or _SYMBOL.fullmatch(symbol) is None:
        return _fail("invalid-symbol", "symbol does not match the documented stock or pair form.")
    if action not in ACTIONS:
        return _fail(
            "invalid-action",
            "Alpaca stock examples use buy, sell, or close.",
        )
    if "quantity" in parsed and not positive(parsed["quantity"]):
        return _fail("invalid-quantity", "quantity must be greater than 0 when it is sent.")
    if "quantity_type" in parsed and parsed["quantity_type"] not in QUANTITY_TYPES:
        return _fail(
            "invalid-quantity-type",
            "quantity_type is not fixed, cash, or percent_of_equity.",
        )
    for price_name in ("limit_price", "stop_price"):
        if price_name in parsed and not positive(parsed[price_name]):
            return _fail("invalid-price", f"{price_name} must be greater than 0 when it is sent.")

    if "limit_price" in parsed and "stop_price" in parsed:
        shape = "stop_limit"
    elif "limit_price" in parsed:
        shape = "limit"
    elif "stop_price" in parsed:
        shape = "stop"
    else:
        shape = "market"

    sender = redact(parsed)
    signal = {
        "provider": "signalstack",
        "order_shape": shape,
        "quantity_omitted": "quantity" not in parsed,
        "quantity_defaulted": False,
        "sender": sender if isinstance(sender, dict) else {},
    }
    return Validation(
        True,
        "broker-forwarding-disabled",
        "Payload matches the Alpaca stock examples.",
        signal,
    )
