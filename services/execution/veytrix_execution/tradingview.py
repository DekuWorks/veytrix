"""Paper recorder for a TradingView alert message.

TradingView documents an HTTP POST whose body is the alert message. JSON uses
`application/json`. Anything else uses `text/plain`. There is no order schema
in that document. This recorder stores the message and does not turn fields
into a price, a size, or a broker request.
"""

from __future__ import annotations

import json

from veytrix_execution.audit import Validation, redact
from veytrix_execution.limits import MAX_BODY_BYTES
from veytrix_execution.payload import media_type

_JSON = "application/json"
_TEXT = "text/plain"


def _fail(code: str, message: str, *, store: bool = True) -> Validation:
    return Validation(False, code, message, {}, store)


def validate_tradingview(payload: object, content_type: str | None = None) -> Validation:
    declared = media_type(content_type)
    if isinstance(payload, bytes):
        if len(payload) > MAX_BODY_BYTES:
            return _fail("payload-too-large", "Alert message exceeds 16384 bytes.", store=False)
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError:
            return _fail("malformed-message", "Alert message is not UTF-8.")
    elif isinstance(payload, str):
        text = payload
        if len(text.encode("utf-8")) > MAX_BODY_BYTES:
            return _fail("payload-too-large", "Alert message exceeds 16384 bytes.", store=False)
    elif isinstance(payload, dict | list):
        text = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        if declared is None:
            declared = _JSON
    else:
        return _fail("malformed-message", "Alert message must be text or JSON.")

    if declared is None:
        declared = _TEXT
    if declared not in {_JSON, _TEXT}:
        return _fail("unsupported-content-type", "TradingView documents JSON or plain text.")

    if declared == _JSON:
        try:
            parsed: object = payload if isinstance(payload, dict | list) else json.loads(text)
        except json.JSONDecodeError:
            return _fail("malformed-json", "Content type is JSON but the body is not.")
        message: object = redact(parsed)
    else:
        if isinstance(payload, dict | list):
            return _fail("malformed-message", "A JSON value was passed with a text content type.")
        message = text

    signal = {
        "provider": "tradingview",
        "content_type": declared,
        "message": message,
        "interpreted_as_order": False,
        "quote": None,
    }
    return Validation(
        True,
        "broker-forwarding-disabled",
        "Alert message stored. It is not an order.",
        signal,
    )
