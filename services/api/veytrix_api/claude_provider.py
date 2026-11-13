"""One server-side language provider for every desk.

The browser never sees the key and never calls Anthropic. There are no tools.
A missing key stays on the deterministic mock. A present key is probed once.
Only a successful probe may mark a line model_generated.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Literal

from veytrix_api.comms import roster

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-haiku-4-5"
SpeechOrigin = Literal["simulated", "model_generated"]
ClaudeState = Literal["connected", "disconnected"]

_COMMON = (
    "English only. One short sentence. You have no tools. "
    "You cannot submit an order, sign, transfer funds, or change a permission. "
    "live_execution is false. Aegis risk checks are not decided by this sentence. "
    "Futures research is simulation only."
)

_ROLE = {
    "SUPERVISOR-01": (
        "You are Roads, the coordinator. You cannot grant permissions, move money, "
        "or bypass Aegis."
    ),
    "DAY-01": "You are Dayvid on the day desk. You read the session. You do not trade.",
    "STOCK-01": "You are Vex on the stock desk. You read stored signals. You do not trade.",
    "CRYPTO-01": "You are Nyx on the crypto desk. You read stored prices. You do not trade.",
    "DEFI-01": "You are Cipher on the DeFi desk. You cannot sign or broadcast.",
    "ETF-01": "You are Lyra on the ETF desk. You read stored instruments. You do not trade.",
    "RESEARCH-01": "You are Astra on the research desk. You read notes. You do not trade.",
    "RISK-01": "You are Aegis. Your risk decision is deterministic and not this sentence.",
    "TREASURY-01": "You are Midas on the treasury desk. You cannot move funds.",
    "FUTURES-01": "You are Futures. Research and simulation only. No broker account.",
}

_TASK = {
    "SUPERVISOR-01": "Coordinating the floor.",
    "DAY-01": "Reading the session ledger.",
    "STOCK-01": "Reading stored SMA signals.",
    "CRYPTO-01": "Reading stored price bars.",
    "DEFI-01": "Reading paper swaps. Cannot sign.",
    "ETF-01": "Reading stored ETF instruments.",
    "RESEARCH-01": "Reading notes and events.",
    "RISK-01": "Reading the paper risk policy.",
    "TREASURY-01": "Reading paper fills. No transfer.",
    "FUTURES-01": "Research only. No Topstep account.",
}


class ClaudeError(RuntimeError):
    def __init__(self, error_class: str) -> None:
        super().__init__(error_class)
        self.error_class = error_class


@dataclass(frozen=True)
class Speech:
    origin: SpeechOrigin
    text: str
    claude: ClaudeState
    connected: bool
    error_class: str | None = None


@dataclass(frozen=True)
class Probe:
    claude: ClaudeState
    connected: bool
    credential_present: bool
    error_class: str | None
    speech_origin: SpeechOrigin


_cached: Probe | None = None


def reset() -> None:
    global _cached
    _cached = None


def credential_present() -> bool:
    raw = os.environ.get("ANTHROPIC_API_KEY")
    return bool(raw and raw.strip())


def mock_line(code: str) -> str:
    try:
        desk = roster.desk_for(code)
        name = desk.name
    except KeyError:
        name = code
    task = _TASK.get(code, "Standing by.")
    return f"{name}. Simulated. {task} No model was called. No order is sent."


def _model_name() -> str:
    raw = os.environ.get("ANTHROPIC_MODEL", "").strip()
    return raw or DEFAULT_MODEL


def _complete(system: str, user: str, transport) -> str:
    if transport is not None:
        status, payload = transport(system, user)
    else:
        key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not key:
            raise ClaudeError("missing_key")
        body = json.dumps(
            {
                "model": _model_name(),
                "max_tokens": 32,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            }
        ).encode()
        request = urllib.request.Request(
            ANTHROPIC_URL,
            data=body,
            headers={
                "content-type": "application/json",
                "anthropic-version": "2023-06-01",
                "x-api-key": key,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                status = response.status
                payload = json.loads(response.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as exc:
            raise ClaudeError(f"HTTPError:{exc.code}") from None
        except urllib.error.URLError:
            raise ClaudeError("URLError") from None
        except TimeoutError:
            raise ClaudeError("TimeoutError") from None
    if status != 200 or not isinstance(payload, dict):
        raise ClaudeError(f"HTTPError:{status}")
    text = ""
    content = payload.get("content")
    if isinstance(content, list):
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                text += str(part.get("text") or "")
    text = " ".join(text.split())
    if not text:
        raise ClaudeError("empty_completion")
    return text[:400]


def probe(transport=None) -> Probe:
    """One connectivity check. No network call when the key is absent."""

    global _cached
    if transport is None and _cached is not None:
        return _cached
    if not credential_present() and transport is None:
        result = Probe(
            claude="disconnected",
            connected=False,
            credential_present=False,
            error_class=None,
            speech_origin="simulated",
        )
        _cached = result
        return result
    try:
        _complete(
            _COMMON,
            "Reply with the single English word ready.",
            transport,
        )
    except ClaudeError as exc:
        result = Probe(
            claude="disconnected",
            connected=False,
            credential_present=True,
            error_class=exc.error_class,
            speech_origin="simulated",
        )
    else:
        result = Probe(
            claude="connected",
            connected=True,
            credential_present=True,
            error_class=None,
            speech_origin="model_generated",
        )
    if transport is None:
        _cached = result
    return result


def speak(code: str, transport=None) -> Speech:
    """Shared provider. Role text differs. No desk receives a trading tool."""

    status = probe(transport)
    if not status.connected:
        return Speech(
            origin="simulated",
            text=mock_line(code),
            claude="disconnected",
            connected=False,
            error_class=status.error_class,
        )
    role = _ROLE.get(code, "You are a research desk. You do not trade.")
    try:
        text = _complete(
            f"{role} {_COMMON}",
            "State your current paper-research task in one English sentence.",
            transport,
        )
    except ClaudeError as exc:
        return Speech(
            origin="simulated",
            text=mock_line(code),
            claude="disconnected",
            connected=False,
            error_class=exc.error_class,
        )
    return Speech(
        origin="model_generated",
        text=text,
        claude="connected",
        connected=True,
    )
