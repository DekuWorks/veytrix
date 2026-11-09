"""Model routing stays local and cannot spend or trade by default."""

from decimal import Decimal

from fastapi.testclient import TestClient

from veytrix_api.main import create_app
from veytrix_api.model_router import route_task
from veytrix_api.settings import Settings


def test_deterministic_task_uses_no_model() -> None:
    decision = route_task(
        agent_code="RISK-01",
        task="position_size",
        provider="openai",
        paid_inference_enabled=True,
        monthly_ceiling_usd=Decimal("20"),
        spent_usd=Decimal("0"),
        ollama_configured=False,
    )
    assert decision.persona == "Aegis"
    assert decision.provider == "none"
    assert decision.allowed is True
    assert decision.reason == "deterministic"
    assert decision.estimated_usd == Decimal("0")
    assert decision.execution_permitted is False


def test_paid_provider_is_paused_by_default() -> None:
    decision = route_task(
        agent_code="RESEARCH-01",
        task="summarise_note",
        provider="cursor",
        paid_inference_enabled=False,
        monthly_ceiling_usd=Decimal("0"),
        spent_usd=Decimal("0"),
        ollama_configured=False,
    )
    assert decision.persona == "Astra"
    assert decision.allowed is False
    assert decision.reason == "paid_inference_paused"
    assert decision.paid is True


def test_paid_provider_does_not_run_even_when_spending_is_allowed() -> None:
    decision = route_task(
        agent_code="TREASURY-01",
        task="summarise_note",
        provider="openai",
        paid_inference_enabled=True,
        monthly_ceiling_usd=Decimal("10"),
        spent_usd=Decimal("0"),
        ollama_configured=False,
    )
    assert decision.allowed is False
    assert decision.reason == "paid_provider_not_configured"


def test_exhausted_ceiling_pauses_paid_inference() -> None:
    decision = route_task(
        agent_code="DAY-01",
        task="summarise_note",
        provider="anthropic",
        paid_inference_enabled=True,
        monthly_ceiling_usd=Decimal("5"),
        spent_usd=Decimal("5"),
        ollama_configured=True,
    )
    assert decision.persona == "Dayvid"
    assert decision.reason == "paid_inference_paused"


def test_ollama_requires_configuration() -> None:
    missing = route_task(
        agent_code="CRYPTO-01",
        task="summarise_note",
        provider="ollama",
        paid_inference_enabled=False,
        monthly_ceiling_usd=Decimal("0"),
        spent_usd=Decimal("0"),
        ollama_configured=False,
    )
    ready = route_task(
        agent_code="CRYPTO-01",
        task="summarise_note",
        provider="ollama",
        paid_inference_enabled=False,
        monthly_ceiling_usd=Decimal("0"),
        spent_usd=Decimal("0"),
        ollama_configured=True,
    )
    assert missing.reason == "ollama_not_configured"
    assert ready.allowed is True
    assert ready.paid is False
    assert ready.estimated_usd == Decimal("0")


def _client() -> TestClient:
    settings = Settings(
        veytrix_env="local",
        veytrix_enable_live_broker=False,
        database_url="postgresql+psycopg://veytrix:local-dev-only@127.0.0.1:1/veytrix",
        paid_inference_enabled=False,
        ai_monthly_ceiling_usd=Decimal("0"),
        ollama_url="",
    )
    return TestClient(create_app(settings))


def test_posture_says_cursor_does_not_run_the_desks() -> None:
    client = _client()
    response = client.get("/api/v1/inference/posture")
    assert response.status_code == 200
    body = response.json()
    assert body["cursor_subscription_runs_agents"] is False
    assert body["paid_inference_enabled"] is False
    assert body["auto_purchase"] is False
    assert body["execution_permitted"] is False
    assert body["personas"]["RESEARCH-01"] == "Astra"
    assert "FUTURES-01" not in body["personas"]


def test_route_endpoint_refuses_cursor_as_a_runtime() -> None:
    client = _client()
    response = client.post(
        "/api/v1/inference/route",
        json={"agent_code": "STOCK-01", "task": "summarise_note", "provider": "cursor"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["persona"] == "Vex"
    assert body["allowed"] is False
    assert body["order_submitted"] is False
