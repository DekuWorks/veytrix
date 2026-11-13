"""The shared desk model stays simulated until a Claude probe succeeds."""

import ast
from pathlib import Path

import pytest

from veytrix_api.claude_provider import mock_line, probe, reset, speak

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _clear(monkeypatch: pytest.MonkeyPatch) -> None:
    reset()
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def test_missing_key_is_simulated_and_does_not_call_out() -> None:
    called = False

    def transport(_system: str, _user: str):
        nonlocal called
        called = True
        return 200, {"content": [{"type": "text", "text": "ready"}]}

    status = probe()
    line = speak("SUPERVISOR-01")

    assert called is False
    assert status.credential_present is False
    assert status.claude == "disconnected"
    assert status.connected is False
    assert status.speech_origin == "simulated"
    assert line.origin == "simulated"
    assert line.origin != "model_generated"
    assert "No model was called." in line.text
    assert "Roads" in line.text


def test_successful_probe_marks_speech_model_generated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-a-real-secret")
    systems: list[str] = []

    def transport(system: str, user: str):
        systems.append(system)
        if "ready" in user:
            return 200, {"content": [{"type": "text", "text": "ready"}]}
        return 200, {"content": [{"type": "text", "text": "Reading the local research notes."}]}

    status = probe(transport)
    roads = speak("SUPERVISOR-01", transport)
    futures = speak("FUTURES-01", transport)

    assert status.connected is True
    assert status.claude == "connected"
    assert roads.origin == "model_generated"
    assert any("Roads" in system and "grant permissions" in system for system in systems)
    assert futures.origin == "model_generated"
    assert futures.text == "Reading the local research notes."
    assert "test-key" not in roads.text
    assert "test-key" not in futures.text


def test_failed_probe_stays_disconnected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-a-real-secret")

    def transport(_system: str, _user: str):
        raise __import__("veytrix_api.claude_provider", fromlist=["ClaudeError"]).ClaudeError(
            "HTTPError:401"
        )

    status = probe(transport)
    line = speak("RISK-01", transport)

    assert status.connected is False
    assert status.claude == "disconnected"
    assert status.error_class == "HTTPError:401"
    assert line.origin == "simulated"
    assert line.origin != "model_generated"
    assert "Aegis" in mock_line("RISK-01")


def test_provider_has_no_trading_imports() -> None:
    banned = {"alpaca", "httpx", "veytrix_ai", "veytrix_quant"}
    path = ROOT / "services" / "api" / "veytrix_api" / "claude_provider.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split(".")[0] not in banned
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] not in banned
    source = path.read_text(encoding="utf-8")
    assert '"tools"' not in source
    assert "Mac01Engine" not in source
