"""Grok assistant controls, with no key file and no network call."""

import socket
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from grok_assistant.service import (
    DOCUMENTED_MODEL,
    RESPONSES_PATH,
    Actor,
    AuthBoundary,
    GrokAssistant,
    LocalRateLimiter,
    OfflineTransport,
    ProviderRequest,
    ProviderResult,
    UsageLedger,
    api_key_from_env,
    build_responses_body,
)

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "apps" / "grok-assistant"
T0 = datetime(2026, 11, 13, 17, 0, tzinfo=UTC)
PROMPT = "Summarise the selected note."


class FakeTransport:
    def __init__(
        self,
        result: ProviderResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.calls: list[ProviderRequest] = []
        self.result = result or ProviderResult(
            200,
            {
                "id": "resp_test",
                "usage": {"input_tokens": 3, "output_tokens": 4},
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "stub answer"}],
                    }
                ],
            },
        )
        self.error = error

    def send(self, request: ProviderRequest) -> ProviderResult:
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        return self.result


def service(
    *,
    api_key: str | None = "short-key",
    limit: int = 2,
    transport: FakeTransport | OfflineTransport | None = None,
    retention_seconds: int = 86_400,
) -> tuple[GrokAssistant, FakeTransport | OfflineTransport]:
    auth = AuthBoundary(
        {
            "alpha": Actor("tenant-one", "user-a"),
            "beta": Actor("tenant-two", "user-a"),
        }
    )
    seam = transport or FakeTransport()
    assistant = GrokAssistant(
        api_key=api_key,
        auth=auth,
        limiter=LocalRateLimiter(limit=limit, window_seconds=60),
        ledger=UsageLedger(retention_seconds=retention_seconds),
        transport=seam,
    )
    return assistant, seam


def test_missing_key_is_unconfigured_and_does_not_call_out() -> None:
    assistant, seam = service(api_key=api_key_from_env({}))
    assert isinstance(seam, FakeTransport)

    status = assistant.status()
    result = assistant.complete(authorization="Bearer alpha", prompt=PROMPT, now=T0)

    assert status["configured"] is False
    assert status["state"] == "unconfigured"
    assert status["endpoint"] == RESPONSES_PATH
    assert status["provider_store"] is False
    assert result["error"] == "unconfigured"
    assert result["text"] is None
    assert seam.calls == []
    assert assistant.ledger.for_actor("tenant-one", "user-a") == []


def test_tenant_isolation_and_rate_limit_without_a_network_socket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("socket opened")

    monkeypatch.setattr(socket, "socket", boom)
    assistant, seam = service(limit=2)
    assert isinstance(seam, FakeTransport)

    first = assistant.complete(authorization="Bearer alpha", prompt=PROMPT, now=T0)
    second = assistant.complete(
        authorization="Bearer alpha",
        prompt=PROMPT,
        now=T0 + timedelta(seconds=1),
    )
    blocked = assistant.complete(
        authorization="Bearer alpha",
        prompt=PROMPT,
        now=T0 + timedelta(seconds=2),
    )
    other = assistant.complete(
        authorization="Bearer beta",
        prompt=PROMPT,
        now=T0 + timedelta(seconds=3),
    )

    assert first["ok"] is True and first["text"] == "stub answer"
    assert second["ok"] is True
    assert blocked["error"] == "rate_limited"
    assert other["ok"] is True
    assert len(seam.calls) == 3
    assert seam.calls[0].body["store"] is False
    assert seam.calls[0].body["model"] == DOCUMENTED_MODEL
    assert seam.calls[0].body["input"] == PROMPT
    assert seam.calls[0].has_authorization is True
    assert "short-key" not in str(seam.calls[0])

    one = assistant.ledger.for_actor("tenant-one", "user-a")
    two = assistant.ledger.for_actor("tenant-two", "user-a")
    assert [event.status for event in one] == ["ok", "ok", "rate_limited"]
    assert [event.status for event in two] == ["ok"]
    assert PROMPT not in repr(assistant.ledger)
    assert "stub answer" not in repr(assistant.ledger)
    assert "short-key" not in repr(assistant)


def test_unauthorized_invalid_timeout_and_provider_errors_skip_or_record_cleanly() -> None:
    assistant, seam = service()
    assert isinstance(seam, FakeTransport)

    denied = assistant.complete(authorization="Bearer nope", prompt=PROMPT, now=T0)
    empty = assistant.complete(authorization="Bearer alpha", prompt="  ", now=T0)
    assert denied["error"] == "unauthorized"
    assert empty["error"] == "invalid_prompt"
    assert seam.calls == []

    timing_out, timing_seam = service(transport=FakeTransport(error=TimeoutError("slow")))
    timed = timing_out.complete(authorization="Bearer alpha", prompt=PROMPT, now=T0)
    assert isinstance(timing_seam, FakeTransport)
    assert timed["error"] == "timeout"
    assert "slow" not in str(timed["message"])

    offline = GrokAssistant(
        api_key="short-key",
        auth=AuthBoundary({"alpha": Actor("tenant-one", "user-a")}),
        transport=OfflineTransport(),
    )
    down = offline.complete(authorization="Bearer alpha", prompt=PROMPT, now=T0)
    assert down["error"] == "offline"
    assert down["text"] is None

    rejected, rejected_seam = service(
        transport=FakeTransport(result=ProviderResult(429, {"message": "later"}))
    )
    assert rejected.complete(authorization="Bearer alpha", prompt=PROMPT, now=T0)["error"] == (
        "provider_rate_limited"
    )
    failed, _failed_seam = service(transport=FakeTransport(result=ProviderResult(500, {})))
    provider_error = failed.complete(authorization="Bearer alpha", prompt=PROMPT, now=T0)
    assert provider_error["error"] == "provider_error"
    assert isinstance(rejected_seam, FakeTransport)
    assert "short-key" not in str(rejected.complete(authorization=None, prompt=PROMPT, now=T0))


def test_usage_retention_drops_old_rows_and_keeps_prompts_out() -> None:
    assistant, _seam = service(retention_seconds=60)
    assistant.complete(authorization="Bearer alpha", prompt=PROMPT, now=T0)
    kept = assistant.ledger.for_actor("tenant-one", "user-a")
    assert kept[0].status == "ok"
    assert PROMPT not in repr(kept[0])
    assert "stub answer" not in repr(kept[0])

    removed = assistant.ledger.purge(T0 + timedelta(seconds=61))

    assert removed == 1
    assert assistant.ledger.for_actor("tenant-one", "user-a") == []
    assert build_responses_body(PROMPT)["store"] is False


def test_obsidian_plugin_stays_outside_the_trading_system() -> None:
    root = ROOT / "apps" / "obsidian-assistant"
    banned = (
        "veytrix_quant",
        "veytrix_api",
        "veytrix_execution",
        "alpaca",
        "fetch(",
        "requestUrl",
        "createServer",
        "0.0.0.0",
    )
    files = [path for path in root.rglob("*") if path.suffix in {".ts", ".json", ".md"}]
    assert files
    for path in files:
        text = path.read_text(encoding="utf-8")
        for word in banned:
            assert word not in text, path.name


def test_assistant_tree_does_not_import_trading_code() -> None:
    banned = (
        "veytrix_quant",
        "veytrix_api",
        "veytrix_risk",
        "veytrix_execution",
        "alpaca",
        "Mac01",
        "subprocess",
        "urlopen",
        "import socket",
        "from socket",
    )
    sources = [path for path in APP.rglob("*.py")]
    assert sources
    for path in sources:
        text = path.read_text(encoding="utf-8")
        for word in banned:
            assert word not in text, path.name
        assert "open(" not in text
