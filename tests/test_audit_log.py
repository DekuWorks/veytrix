"""Read-only size audit log. The route does not calculate a size or submit an order."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from veytrix_api.db import get_db
from veytrix_api.main import create_app
from veytrix_api.models import AuditEvent
from veytrix_api.settings import Settings

LOCAL_URL = "postgresql+psycopg://veytrix:local-dev-only@127.0.0.1:5433/veytrix"


def _limit(statement: object) -> int | None:
    clause = getattr(statement, "_limit_clause", None)
    if clause is None:
        return None
    value = getattr(clause, "value", None)
    if isinstance(value, int):
        return value
    inner = getattr(value, "value", None)
    if isinstance(inner, int):
        return inner
    return None


def _payload(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "symbol": "ETH-USD",
        "shares": 4,
        "binding_constraint": "allocation",
        "execution_permitted": False,
        "order_submitted": False,
    }
    body.update(overrides)
    return body


def _event(**overrides: object) -> AuditEvent:
    values: dict[str, object] = {
        "id": uuid4(),
        "correlation_id": "size-audit-1",
        "action": "risk.size.recorded",
        "payload": _payload(),
        "created_at": datetime(2026, 11, 8, 4, 40, tzinfo=UTC),
    }
    values.update(overrides)
    return AuditEvent(**values)


class _LogSession:
    def __init__(self, rows: list[AuditEvent], *, fail: bool = False) -> None:
        self.rows = rows
        self.fail = fail
        self.added: list[object] = []

    def scalars(self, statement: object) -> list[AuditEvent]:
        if self.fail:
            raise RuntimeError("database down")
        rows = sorted(self.rows, key=lambda row: (row.created_at, str(row.id)), reverse=True)
        limit = _limit(statement)
        if limit is not None:
            return rows[:limit]
        return rows

    def add(self, row: object) -> None:
        self.added.append(row)

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None


def _client(session: _LogSession) -> tuple[object, TestClient]:
    app = create_app()

    def override():
        yield session

    app.dependency_overrides[get_db] = override
    return app, TestClient(app)


def test_audit_log_reads_a_size_row_and_cannot_post() -> None:
    older = _event(created_at=datetime(2026, 11, 8, 4, 0, tzinfo=UTC), correlation_id="older-row")
    newer = _event(
        created_at=datetime(2026, 11, 8, 5, 0, tzinfo=UTC),
        correlation_id="newer-row",
        payload=_payload(symbol="BTC-USD", shares=2, binding_constraint="risk"),
    )
    session = _LogSession([older, newer])
    app, client = _client(session)
    with client:
        listed = client.get("/api/v1/audit/log")
        posted = client.post("/api/v1/audit/log", json={"action": "risk.size.recorded"})
        removed = client.delete("/api/v1/audit/log")

    assert listed.status_code == 200
    body = listed.json()
    assert body["source"] == "local_audit_log"
    assert body["execution_permitted"] is False
    assert body["order_submitted"] is False
    assert [item["correlation_id"] for item in body["events"]] == ["newer-row", "older-row"]
    assert body["events"][0]["symbol"] == "BTC-USD"
    assert body["events"][0]["shares"] == 2
    assert body["events"][0]["action"] == "risk.size.recorded"
    assert body["events"][0]["order_submitted"] is False
    assert "payload" not in body["events"][0]
    assert posted.status_code == 405
    assert removed.status_code == 405
    assert set(app.openapi()["paths"]["/api/v1/audit/log"]) == {"get"}
    assert not any(path.endswith("/events") for path in app.openapi()["paths"])
    assert session.added == []


def test_audit_log_hides_a_row_that_claims_an_order() -> None:
    claimed = _event(payload=_payload(order_submitted=True))
    _app, client = _client(_LogSession([claimed]))
    with client:
        listed = client.get("/api/v1/audit/log")
    assert listed.status_code == 503
    assert listed.json()["detail"] == "Audit log is unavailable."
    assert "ETH-USD" not in listed.text


def test_audit_log_hides_an_unknown_action_or_extra_key() -> None:
    _app, client = _client(_LogSession([_event(action="order.submitted")]))
    with client:
        unknown = client.get("/api/v1/audit/log")
    assert unknown.status_code == 503
    assert "order.submitted" not in unknown.text

    extra = _payload()
    extra["account_number"] = "hidden"
    _app, client = _client(_LogSession([_event(payload=extra)]))
    with client:
        leaked = client.get("/api/v1/audit/log")
    assert leaked.status_code == 503
    assert "hidden" not in leaked.text
    assert "account_number" not in leaked.text


def test_audit_log_returns_the_newest_twenty() -> None:
    base = datetime(2026, 11, 8, 4, 0, tzinfo=UTC)
    rows = [
        _event(
            id=uuid4(),
            created_at=base.replace(minute=index),
            correlation_id=f"row-{index}",
            payload=_payload(shares=index),
        )
        for index in range(21)
    ]
    _app, client = _client(_LogSession(rows))
    with client:
        listed = client.get("/api/v1/audit/log")
    assert listed.status_code == 200
    events = listed.json()["events"]
    assert len(events) == 20
    assert events[0]["shares"] == 20
    assert events[-1]["shares"] == 1


def test_audit_log_is_unavailable_when_the_store_fails() -> None:
    _app, client = _client(_LogSession([], fail=True))
    with client:
        listed = client.get("/api/v1/audit/log")
    assert listed.status_code == 503
    assert listed.json()["detail"] == "Audit log is unavailable."


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
def test_audit_log_reads_local_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
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
        listed = client.get("/api/v1/audit/log")
        posted = client.post("/api/v1/audit/log", json={})
    assert listed.status_code == 200
    body = listed.json()
    assert body["source"] == "local_audit_log"
    assert body["execution_permitted"] is False
    assert body["order_submitted"] is False
    assert all(item["action"] == "risk.size.recorded" for item in body["events"])
    assert all(item["order_submitted"] is False for item in body["events"])
    assert posted.status_code == 405
