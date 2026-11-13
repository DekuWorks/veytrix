"""xAI Responses API client seam with local controls.

The documented path for new integrations is POST /v1/responses on api.x.ai.
Chat completions are the legacy path and are not used here. Provider storage
defaults to 30 days; every body this module builds sends store=false.

No method opens a socket. The default transport raises OfflineError. A real
network call is a later review, and it still must not read a key from a file.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

RESPONSES_ORIGIN = "https://api.x.ai"
RESPONSES_PATH = "/v1/responses"
DOCUMENTED_MODEL = "grok-4.7"
PROVIDER_STORE = False
LOCAL_PROMPT_RETENTION = "none"
DEFAULT_LIMIT = 30
DEFAULT_WINDOW_SECONDS = 60
DEFAULT_RETENTION_SECONDS = 86_400
MAX_PROMPT_CHARS = 8_000


class OfflineError(RuntimeError):
    """The transport was asked to send and this build has no network client."""


@dataclass(frozen=True)
class Actor:
    tenant_id: str
    user_id: str


@dataclass(frozen=True)
class UsageEvent:
    tenant_id: str
    user_id: str
    at: datetime
    status: str
    input_units: int | None = None
    output_units: int | None = None


@dataclass(frozen=True)
class ProviderRequest:
    url: str
    body: dict[str, object]
    has_authorization: bool


@dataclass(frozen=True)
class ProviderResult:
    status_code: int
    body: Mapping[str, object]


class Transport(Protocol):
    def send(self, request: ProviderRequest) -> ProviderResult: ...


class OfflineTransport:
    def send(self, request: ProviderRequest) -> ProviderResult:
        raise OfflineError("This build does not call the network.")


class AuthBoundary:
    def __init__(self, actors_by_credential: Mapping[str, Actor]) -> None:
        self._actors = dict(actors_by_credential)

    def authenticate(self, header: str | None) -> Actor | None:
        if header is None or not header.startswith("Bearer "):
            return None
        credential = header.removeprefix("Bearer ").strip()
        if not credential:
            return None
        return self._actors.get(credential)


class LocalRateLimiter:
    def __init__(
        self,
        limit: int = DEFAULT_LIMIT,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
    ) -> None:
        if limit < 1 or window_seconds < 1:
            raise ValueError("limit and window must be at least 1.")
        self.limit = limit
        self.window = timedelta(seconds=window_seconds)
        self._hits: dict[tuple[str, str], list[datetime]] = {}

    def allow(self, tenant_id: str, user_id: str, now: datetime) -> bool:
        key = (tenant_id, user_id)
        recent = [item for item in self._hits.get(key, []) if now - item < self.window]
        if len(recent) >= self.limit:
            self._hits[key] = recent
            return False
        recent.append(now)
        self._hits[key] = recent
        return True


class UsageLedger:
    def __init__(self, retention_seconds: int = DEFAULT_RETENTION_SECONDS) -> None:
        self.retention = timedelta(seconds=retention_seconds)
        self._events: list[UsageEvent] = []

    def add(self, event: UsageEvent) -> None:
        self._events.append(event)

    def for_actor(self, tenant_id: str, user_id: str) -> list[UsageEvent]:
        return [
            event
            for event in self._events
            if event.tenant_id == tenant_id and event.user_id == user_id
        ]

    def purge(self, now: datetime) -> int:
        before = len(self._events)
        self._events = [event for event in self._events if now - event.at <= self.retention]
        return before - len(self._events)


def api_key_from_env(environ: Mapping[str, str] | None = None) -> str | None:
    """Read XAI_API_KEY from a mapping. There is no file loader."""

    source = os.environ if environ is None else environ
    value = source.get("XAI_API_KEY", "").strip()
    return value or None


def build_responses_body(prompt: str, model: str = DOCUMENTED_MODEL) -> dict[str, object]:
    return {"model": model, "input": prompt, "store": PROVIDER_STORE}


class GrokAssistant:
    def __init__(
        self,
        *,
        api_key: str | None,
        auth: AuthBoundary,
        limiter: LocalRateLimiter | None = None,
        ledger: UsageLedger | None = None,
        transport: Transport | None = None,
        model: str = DOCUMENTED_MODEL,
    ) -> None:
        self._api_key = api_key.strip() if isinstance(api_key, str) and api_key.strip() else None
        self._auth = auth
        self._limiter = limiter or LocalRateLimiter()
        self._ledger = ledger or UsageLedger()
        self._transport = transport or OfflineTransport()
        self._model = model

    def __repr__(self) -> str:
        state = "ready" if self._api_key else "unconfigured"
        return f"GrokAssistant(state={state})"

    @property
    def ledger(self) -> UsageLedger:
        return self._ledger

    def status(self) -> dict[str, object]:
        configured = self._api_key is not None
        return {
            "configured": configured,
            "state": "ready" if configured else "unconfigured",
            "endpoint": RESPONSES_PATH,
            "provider_store": PROVIDER_STORE,
            "local_prompt_retention": LOCAL_PROMPT_RETENTION,
            "network_called": False,
        }

    def complete(
        self,
        *,
        authorization: str | None,
        prompt: str,
        now: datetime,
    ) -> dict[str, object]:
        if self._api_key is None:
            return self._error("unconfigured", "XAI_API_KEY is not set. No request was sent.")
        actor = self._auth.authenticate(authorization)
        if actor is None:
            return self._error("unauthorized", "A bearer credential for this service is required.")
        if not self._limiter.allow(actor.tenant_id, actor.user_id, now):
            self._remember(actor, now, "rate_limited")
            return self._error("rate_limited", "Local request limit reached.")
        if not isinstance(prompt, str) or not prompt.strip():
            self._remember(actor, now, "invalid_prompt")
            return self._error("invalid_prompt", "Prompt is empty.")
        if len(prompt) > MAX_PROMPT_CHARS:
            self._remember(actor, now, "invalid_prompt")
            return self._error("invalid_prompt", "Prompt is too long.")

        request = ProviderRequest(
            url=f"{RESPONSES_ORIGIN}{RESPONSES_PATH}",
            body=build_responses_body(prompt, self._model),
            has_authorization=True,
        )
        try:
            result = self._transport.send(request)
        except OfflineError:
            self._remember(actor, now, "offline")
            return self._error("offline", "No network call is implemented in this build.")
        except TimeoutError:
            self._remember(actor, now, "timeout")
            return self._error("timeout", "The provider seam timed out.")
        return self._from_provider(actor, now, result)

    def _from_provider(
        self,
        actor: Actor,
        now: datetime,
        result: ProviderResult,
    ) -> dict[str, object]:
        if result.status_code == 401:
            self._remember(actor, now, "provider_unauthorized")
            return self._error("provider_unauthorized", "The provider rejected the credential.")
        if result.status_code == 429:
            self._remember(actor, now, "provider_rate_limited")
            return self._error("provider_rate_limited", "The provider asked us to slow down.")
        if result.status_code != 200:
            self._remember(actor, now, "provider_error")
            return self._error("provider_error", "The provider returned an error.")
        text = _output_text(result.body)
        if text is None:
            self._remember(actor, now, "provider_error")
            return self._error("provider_error", "The provider body had no output text.")
        usage = result.body.get("usage")
        input_units, output_units = _units(usage)
        self._remember(actor, now, "ok", input_units, output_units)
        return {
            "ok": True,
            "error": None,
            "text": text,
            "provider_store": PROVIDER_STORE,
            "local_prompt_retention": LOCAL_PROMPT_RETENTION,
        }

    def _remember(
        self,
        actor: Actor,
        now: datetime,
        status: str,
        input_units: int | None = None,
        output_units: int | None = None,
    ) -> None:
        self._ledger.add(
            UsageEvent(
                tenant_id=actor.tenant_id,
                user_id=actor.user_id,
                at=now,
                status=status,
                input_units=input_units,
                output_units=output_units,
            )
        )

    @staticmethod
    def _error(code: str, message: str) -> dict[str, object]:
        return {
            "ok": False,
            "error": code,
            "message": message,
            "text": None,
            "provider_store": PROVIDER_STORE,
            "local_prompt_retention": LOCAL_PROMPT_RETENTION,
        }


def _units(usage: object) -> tuple[int | None, int | None]:
    if not isinstance(usage, Mapping):
        return None, None
    return _count(usage.get("input_tokens")), _count(usage.get("output_tokens"))


def _count(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value < 0:
        return None
    return value


def _output_text(body: Mapping[str, object]) -> str | None:
    output = body.get("output")
    if not isinstance(output, list):
        return None
    for item in output:
        if not isinstance(item, Mapping) or item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if isinstance(part, Mapping) and part.get("type") == "output_text":
                text = part.get("text")
                if isinstance(text, str):
                    return text
    return None
