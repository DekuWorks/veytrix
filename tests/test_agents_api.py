"""Read-only registry and local system status. Neither route submits an order."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from veytrix_api.db import get_db
from veytrix_api.main import create_app
from veytrix_api.models import AgentPermissionRow, AgentRow
from veytrix_api.schemas import AGENT_CODES, DENIED_TOOLS
from veytrix_api.settings import Settings

LOCAL_URL = "postgresql+psycopg://veytrix:local-dev-only@127.0.0.1:5433/veytrix"


def _desk(code: str, **overrides: object) -> AgentRow:
    values: dict[str, object] = {
        "id": uuid4(),
        "code": code,
        "display_name": code.title(),
        "desk": "desk",
        "status": "disabled",
        "paper_only": True,
        "can_submit_orders": False,
        "can_sign": False,
        "can_transfer_funds": False,
        "holds_credentials": False,
        "notes": "Registry row only.",
        "created_at": datetime(2026, 11, 8, tzinfo=UTC),
    }
    values.update(overrides)
    return AgentRow(**values)


class _RegistrySession:
    def __init__(self, rows: list[AgentRow], *, fail: bool = False) -> None:
        self.rows = rows
        self.fail = fail
        self.added: list[object] = []

    def execute(self, _statement: object) -> None:
        if self.fail:
            raise RuntimeError("database down")

    def scalars(self, _statement: object) -> list[AgentRow]:
        if self.fail:
            raise RuntimeError("database down")
        return list(self.rows)

    def add(self, row: object) -> None:
        self.added.append(row)

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None


def _client(session: _RegistrySession) -> tuple[object, TestClient]:
    app = create_app()

    def override():
        yield session

    app.dependency_overrides[get_db] = override
    return app, TestClient(app)


def test_agents_route_lists_disabled_desks_and_cannot_post() -> None:
    session = _RegistrySession([_desk(code) for code in AGENT_CODES])
    app, client = _client(session)
    with client:
        listed = client.get("/api/v1/agents")
        posted = client.post("/api/v1/agents", json={"status": "enabled"})
        patched = client.patch("/api/v1/agents/STOCK-01", json={"can_submit_orders": True})

    assert listed.status_code == 200
    body = listed.json()
    assert body["source"] == "local_registry"
    assert body["trading_rights"] == "denied"
    assert body["execution_permitted"] is False
    assert body["order_submitted"] is False
    assert [row["code"] for row in body["agents"]] == sorted(AGENT_CODES)
    assert all(row["status"] == "disabled" for row in body["agents"])
    assert all(row["can_submit_orders"] is False for row in body["agents"])
    assert all(row["can_sign"] is False for row in body["agents"])
    assert all(row["can_transfer_funds"] is False for row in body["agents"])
    assert all(row["holds_credentials"] is False for row in body["agents"])
    assert all(row["permission_effect"] == "deny" for row in body["agents"])
    assert posted.status_code == 405
    assert patched.status_code == 404
    assert "/api/v1/agents/{code}" not in app.openapi()["paths"]
    assert session.added == []
    assert set(app.openapi()["paths"]["/api/v1/agents"]) == {"get"}


def test_agents_route_hides_a_desk_that_could_trade() -> None:
    rows = [_desk(code) for code in AGENT_CODES]
    rows[0].can_submit_orders = True
    _app, client = _client(_RegistrySession(rows))
    with client:
        listed = client.get("/api/v1/agents")
    assert listed.status_code == 503
    assert listed.json()["detail"] == "Agent registry is unavailable."
    assert "SUPERVISOR-01" not in listed.text


def test_agents_route_is_unavailable_when_the_store_fails() -> None:
    _app, client = _client(_RegistrySession([], fail=True))
    with client:
        listed = client.get("/api/v1/agents")
    assert listed.status_code == 503
    assert listed.json()["detail"] == "Agent registry is unavailable."


def test_system_status_counts_desks_without_a_broker_balance() -> None:
    session = _RegistrySession([_desk(code) for code in AGENT_CODES])
    app, client = _client(session)
    with client:
        status = client.get("/api/v1/system/status")
    body = status.json()
    assert status.status_code == 200
    assert body["database"] == "up"
    assert body["agents_registered"] == 9
    assert body["agents_can_trade"] is False
    assert body["order_route"] == "absent"
    assert body["execution_permitted"] is False
    assert body["order_submitted"] is False
    assert body["live_broker"] == "disabled"
    assert "buying_power" not in body
    assert "equity" not in body
    assert set(app.openapi()["paths"]["/api/v1/system/status"]) == {"get"}


def test_system_status_does_not_invent_a_count_when_the_database_is_down() -> None:
    _app, client = _client(_RegistrySession([], fail=True))
    with client:
        status = client.get("/api/v1/system/status")
    body = status.json()
    assert status.status_code == 503
    assert body["database"] == "down"
    assert body["order_route"] == "absent"
    assert "agents_registered" not in body


def _postgres_5433() -> bool:
    if os.environ.get("CI") == "true":
        return False
    try:
        import psycopg

        with psycopg.connect(LOCAL_URL.replace("+psycopg", ""), connect_timeout=2) as connection:
            connection.execute("SELECT 1")
    except Exception:
        return False
    return True


@pytest.mark.skipif(not _postgres_5433(), reason="PostgreSQL is not running on 127.0.0.1:5433.")
def test_agents_route_reads_the_local_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", LOCAL_URL)
    monkeypatch.setenv("VEYTRIX_ENV", "local")
    monkeypatch.setenv("VEYTRIX_ENABLE_LIVE_BROKER", "0")
    app = create_app(
        Settings(
            veytrix_env="local",
            veytrix_enable_live_broker=False,
            database_url=LOCAL_URL,
        )
    )
    with TestClient(app) as client:
        listed = client.get("/api/v1/agents")
        status = client.get("/api/v1/system/status")
        posted = client.post("/api/v1/agents", json={})
    assert listed.status_code == 200
    body = listed.json()
    assert [row["code"] for row in body["agents"]] == sorted(AGENT_CODES)
    assert all(row["status"] == "disabled" for row in body["agents"])
    assert all(row["can_submit_orders"] is False for row in body["agents"])
    assert body["trading_rights"] == "denied"
    assert status.status_code == 200
    assert status.json()["agents_registered"] == 9
    assert status.json()["agents_can_trade"] is False
    assert status.json()["order_route"] == "absent"
    assert posted.status_code == 405


@pytest.mark.skipif(not _postgres_5433(), reason="PostgreSQL is not running on 127.0.0.1:5433.")
def test_size_audit_row_inserts_and_rolls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    from veytrix_api.audit_log import record_size
    from veytrix_api.db import create_db_engine
    from veytrix_api.logging_config import correlation_id_var

    monkeypatch.setenv("DATABASE_URL", LOCAL_URL)
    correlation = "audit-rollback-size"
    engine = create_db_engine(
        Settings(
            veytrix_env="local",
            veytrix_enable_live_broker=False,
            database_url=LOCAL_URL,
        )
    )
    token = correlation_id_var.set(correlation)
    try:
        with Session(engine) as session:
            before = session.scalar(
                text("SELECT count(*) FROM audit_events WHERE correlation_id = :correlation"),
                {"correlation": correlation},
            )
            record_size(session, symbol="BTC-USD", shares=1, binding_constraint="none")
            session.flush()
            seen = session.scalar(
                text(
                    "SELECT payload->>'order_submitted' FROM audit_events "
                    "WHERE correlation_id = :correlation"
                ),
                {"correlation": correlation},
            )
            session.rollback()
        with Session(engine) as session:
            after = session.scalar(
                text("SELECT count(*) FROM audit_events WHERE correlation_id = :correlation"),
                {"correlation": correlation},
            )
    finally:
        correlation_id_var.reset(token)
        engine.dispose()
    assert before == 0
    assert seen == "false"
    assert after == 0


def _permission(agent_id: object, tool_name: str, effect: str = "deny") -> AgentPermissionRow:
    return AgentPermissionRow(
        id=uuid4(),
        agent_id=agent_id,
        tool_name=tool_name,
        effect=effect,
        created_at=datetime(2026, 11, 8, tzinfo=UTC),
    )


class _DeskSession:
    def __init__(
        self,
        agent: AgentRow | None,
        permissions: list[AgentPermissionRow],
        *,
        fail: bool = False,
    ) -> None:
        self.agent = agent
        self.permissions = permissions
        self.fail = fail
        self.added: list[object] = []

    def scalar(self, _statement: object) -> AgentRow | None:
        if self.fail:
            raise RuntimeError("database down")
        return self.agent

    def scalars(self, _statement: object) -> list[AgentPermissionRow]:
        if self.fail:
            raise RuntimeError("database down")
        return list(self.permissions)

    def add(self, row: object) -> None:
        self.added.append(row)

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None


def test_desk_detail_lists_denies_and_cannot_enable() -> None:
    agent = _desk("SUPERVISOR-01", display_name="Supervisor", notes="Registry row only.")
    session = _DeskSession(agent, [_permission(agent.id, tool) for tool in DENIED_TOOLS])
    app, client = _client(session)
    with client:
        detail = client.get("/api/v1/agency/desks/SUPERVISOR-01")
        posted = client.post("/api/v1/agency/desks/SUPERVISOR-01", json={"status": "enabled"})
        patched = client.patch(
            "/api/v1/agency/desks/SUPERVISOR-01",
            json={"can_submit_orders": True},
        )
        enabled = client.post("/api/v1/agency/desks/SUPERVISOR-01/enable")

    assert detail.status_code == 200
    body = detail.json()
    assert body["code"] == "SUPERVISOR-01"
    assert body["status"] == "disabled"
    assert body["running"] is False
    assert body["can_enable"] is False
    assert body["trading_rights"] == "denied"
    assert body["execution_permitted"] is False
    assert body["order_submitted"] is False
    assert body["notes"] == "Registry row only."
    assert [tool["tool_name"] for tool in body["tools"]] == list(DENIED_TOOLS)
    assert all(tool["effect"] == "deny" for tool in body["tools"])
    assert posted.status_code == 405
    assert patched.status_code == 405
    assert enabled.status_code == 404
    assert set(app.openapi()["paths"]["/api/v1/agency/desks/{code}"]) == {"get"}
    assert "/api/v1/agents/{code}" not in app.openapi()["paths"]
    assert session.added == []


def test_desk_detail_hides_a_desk_that_could_trade() -> None:
    agent = _desk("STOCK-01", display_name="Stock desk", can_submit_orders=True)
    session = _DeskSession(agent, [_permission(agent.id, tool) for tool in DENIED_TOOLS])
    _app, client = _client(session)
    with client:
        detail = client.get("/api/v1/agency/desks/STOCK-01")
    assert detail.status_code == 503
    assert detail.json()["detail"] == "Agent registry is unavailable."
    assert "Stock desk" not in detail.text
    assert "submit_order" not in detail.text


def test_desk_detail_hides_an_allow_and_a_secret_note() -> None:
    agent = _desk("RISK-01")
    allowed = [_permission(agent.id, tool) for tool in DENIED_TOOLS]
    allowed[0].effect = "allow"
    _app, client = _client(_DeskSession(agent, allowed))
    with client:
        detail = client.get("/api/v1/agency/desks/RISK-01")
    assert detail.status_code == 503
    assert "allow" not in detail.text

    secret = _desk("RISK-01", notes="api_key sk-should-not-leak")
    _app, client = _client(
        _DeskSession(secret, [_permission(secret.id, tool) for tool in DENIED_TOOLS])
    )
    with client:
        hidden = client.get("/api/v1/agency/desks/RISK-01")
    assert hidden.status_code == 503
    assert "sk-should-not-leak" not in hidden.text


def test_desk_detail_unknown_code_is_not_found() -> None:
    session = _DeskSession(None, [])
    _app, client = _client(session)
    with client:
        missing = client.get("/api/v1/agency/desks/NOPE")
        absent = client.get("/api/v1/agency/desks/DAY-01")
    assert missing.status_code == 404
    assert absent.status_code == 404
    assert session.added == []


@pytest.mark.skipif(not _postgres_5433(), reason="PostgreSQL is not running on 127.0.0.1:5433.")
def test_desk_detail_reads_the_local_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", LOCAL_URL)
    monkeypatch.setenv("VEYTRIX_ENV", "local")
    monkeypatch.setenv("VEYTRIX_ENABLE_LIVE_BROKER", "0")
    app = create_app(
        Settings(
            veytrix_env="local",
            veytrix_enable_live_broker=False,
            database_url=LOCAL_URL,
        )
    )
    with TestClient(app) as client:
        detail = client.get("/api/v1/agency/desks/SUPERVISOR-01")
        missing = client.get("/api/v1/agency/desks/NOPE")
        posted = client.post("/api/v1/agency/desks/SUPERVISOR-01", json={})
    assert detail.status_code == 200
    body = detail.json()
    assert body["code"] == "SUPERVISOR-01"
    assert body["status"] == "disabled"
    assert body["can_enable"] is False
    assert body["running"] is False
    assert body["can_submit_orders"] is False
    assert [tool["tool_name"] for tool in body["tools"]] == list(DENIED_TOOLS)
    assert all(tool["effect"] == "deny" for tool in body["tools"])
    assert "order" in body["notes"].lower()
    assert missing.status_code == 404
    assert posted.status_code == 405
