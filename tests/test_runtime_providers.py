"""Development boots without external accounts. Live mode does not boot."""

import ast
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from veytrix_api.main import create_app
from veytrix_api.providers import MockModel, build_posture
from veytrix_api.settings import (
    DEFAULT_DATABASE_URL,
    LIVE_OWNER_AUTHORIZATION,
    BootRefused,
    Settings,
)

ROOT = Path(__file__).resolve().parents[1]
CREDENTIALS = (
    "ANTHROPIC_API_KEY",
    "ALPACA_PAPER_API_KEY",
    "ALPACA_PAPER_SECRET_KEY",
    "ALPACA_LIVE_API_KEY",
    "ALPACA_LIVE_SECRET_KEY",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "VITE_SUPABASE_URL",
    "VITE_SUPABASE_ANON_KEY",
)


def _local(mode: str = "development") -> Settings:
    return Settings(
        veytrix_env="local",
        veytrix_enable_live_broker=False,
        database_url=DEFAULT_DATABASE_URL,
        veytrix_mode=mode,  # type: ignore[arg-type]
    )


def _clear_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in CREDENTIALS:
        monkeypatch.delenv(name, raising=False)


def test_owner_authorization_constant_is_false() -> None:
    assert LIVE_OWNER_AUTHORIZATION is False


def test_live_mode_refuses_to_boot() -> None:
    with pytest.raises(BootRefused, match="VEYTRIX_MODE is live"):
        create_app(_local("live"))


def test_development_boots_without_alpaca_claude_or_supabase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_credentials(monkeypatch)
    app = create_app(_local("development"))

    assert app.state.settings.veytrix_mode == "development"
    with TestClient(app) as client:
        response = client.get("/api/v1/providers/posture")

    body = response.json()
    assert response.status_code == 200
    assert body["runtime_mode"] == "development"
    assert body["supabase"] == "not_used"
    assert body["live_execution"] is False
    assert body["order_route"] == "absent"
    assert body["model"]["credential_present"] is False
    assert body["model"]["connected"] is False
    assert body["model"]["production_state"] == "disconnected"
    assert body["model"]["connectivity"] == "not_tested"
    assert body["market"]["state"] == "simulated"
    assert body["market"]["price"] is None
    assert body["broker"]["simulated"] == "simulated"
    assert body["broker"]["paper"] == "disconnected"
    assert body["broker"]["live"] == "disabled"
    assert body["broker"]["order_submitted"] is False
    assert body["broker"]["reaches_mac01"] is False
    assert body["broker"]["reaches_alpaca"] is False
    assert body["broker"]["reaches_swap_signing"] is False
    assert "sk-" not in response.text
    assert "ANTHROPIC_API_KEY" not in response.text


def test_missing_alpaca_keeps_simulated_trading(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_credentials(monkeypatch)
    app = create_app(_local("paper"))

    with TestClient(app) as client:
        body = client.get("/api/v1/providers/posture").json()

    assert body["runtime_mode"] == "paper"
    assert body["broker"]["paper"] == "disconnected"
    assert body["broker"]["simulated"] == "simulated"
    assert body["market"]["state"] == "disconnected"
    assert body["broker"]["order_submitted"] is False
    assert body["model"]["reply_origin"] == "simulated"


def test_mock_reply_is_not_tagged_model_generated() -> None:
    first = MockModel().complete("same prompt")
    second = MockModel().complete("same prompt")
    other = MockModel().complete("other prompt")

    assert first == second
    assert first.origin == "simulated"
    assert first.origin != "model_generated"
    assert first.origin != "tool_verified"
    assert first.label == "simulated"
    assert first.connected is False
    assert "No model was called." in first.text
    assert other.text != first.text

    posture = build_posture(_local("development"))
    assert posture.mock_reply.origin == "simulated"
    assert posture.model.reply_origin == "simulated"
    assert posture.model.preferred_production_provider == "claude"
    assert posture.model.connected is False


def test_provider_module_does_not_import_a_network_client() -> None:
    banned = {"alpaca", "httpx", "requests", "anthropic", "veytrix_ai", "veytrix_quant"}
    path = ROOT / "services" / "api" / "veytrix_api" / "providers.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split(".")[0] not in banned
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] not in banned


def test_provider_route_is_get_only() -> None:
    paths = create_app(_local()).openapi()["paths"]
    assert set(paths["/api/v1/providers/posture"]) == {"get"}
    assert "/api/v1/orders" not in paths
