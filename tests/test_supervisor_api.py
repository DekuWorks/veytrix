"""The supervisor routes do not run a tool, call a model, or submit an order."""

from fastapi.testclient import TestClient

from veytrix_api.main import create_app
from veytrix_api.routers import risk as risk_router
from veytrix_api.settings import Settings
from veytrix_api.tool_gate import DENY_TOOLS, READ_TOOLS


def _client() -> TestClient:
    settings = Settings(
        veytrix_env="local",
        veytrix_enable_live_broker=False,
        database_url="postgresql+psycopg://veytrix:local-dev-only@127.0.0.1:1/veytrix",
    )
    return TestClient(create_app(settings))


def test_tool_catalogue_is_read_only_and_cannot_chat(monkeypatch) -> None:
    def fail_size(*_args, **_kwargs):
        raise AssertionError("the catalogue must not size a position")

    monkeypatch.setattr(risk_router, "size_position", fail_size)
    with _client() as client:
        response = client.get("/api/v1/supervisor/tools")
        posted = client.post("/api/v1/supervisor/tools")
        chat = client.post("/api/v1/supervisor/chat", json={"message": "hello"})
        paths = client.app.openapi()["paths"]

    body = response.json()
    assert response.status_code == 200
    assert posted.status_code == 405
    assert chat.status_code == 404
    assert body["source"] == "local_catalogue"
    assert body["model"] == "not_configured"
    assert body["chat"] == "absent"
    assert body["executed"] is False
    assert body["invokes_model"] is False
    assert body["execution_permitted"] is False
    assert body["order_submitted"] is False
    assert [row["name"] for row in body["tools"]] == list(READ_TOOLS) + list(DENY_TOOLS)
    assert all(row["executes"] is False for row in body["tools"])
    assert body["tools"][0]["effect"] == "read"
    assert "does not run the tool" in body["note"]
    assert "submit an order" in body["note"]
    assert set(paths["/api/v1/supervisor/tools"]) == {"get"}
    assert "/api/v1/supervisor/chat" not in paths
    assert not any("approve" in path or "distribution" in path for path in paths)


def test_tool_check_accepts_a_read_and_refuses_the_sizer(monkeypatch) -> None:
    def fail_size(*_args, **_kwargs):
        raise AssertionError("a tool check must not size a position")

    monkeypatch.setattr(risk_router, "size_position", fail_size)
    with _client() as client:
        accepted = client.post(
            "/api/v1/supervisor/tools/check",
            json={"tool_name": "read_desk", "arguments": {"code": "RISK-01"}},
        )
        again = client.post(
            "/api/v1/supervisor/tools/check",
            json={"tool_name": "read_desk", "arguments": {"code": "RISK-01"}},
        )
        sized = client.post(
            "/api/v1/supervisor/tools/check",
            json={"tool_name": "size_position", "arguments": {}},
        )
        numbered = client.post(
            "/api/v1/supervisor/tools/check",
            json={"tool_name": "read_agents", "arguments": {"limit": 1}},
        )
        fetched = client.get("/api/v1/supervisor/tools/check")
        paths = client.app.openapi()["paths"]

    body = accepted.json()
    assert accepted.status_code == 200
    assert again.json() == body
    assert body["decision"] == "accept"
    assert body["reasons"] == []
    assert body["effect"] == "read"
    assert body["executed"] is False
    assert body["invokes_model"] is False
    assert body["execution_permitted"] is False
    assert body["order_submitted"] is False
    assert "did not run the tool" in body["note"]
    assert sized.status_code == 200
    assert sized.json()["decision"] == "deny"
    assert sized.json()["reasons"] == ["tool"]
    assert sized.json()["executed"] is False
    assert numbered.status_code == 422
    assert fetched.status_code == 405
    assert set(paths["/api/v1/supervisor/tools/check"]) == {"post"}
    assert "order_id" not in body
