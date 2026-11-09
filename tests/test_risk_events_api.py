"""The risk event log reads stored sizes and does not store previews."""

from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from veytrix_api.db import get_db
from veytrix_api.main import create_app
from veytrix_api.models import AuditEvent

PATH = "/api/v1/risk/log"


class _Rows:
    def __init__(self, rows: list[AuditEvent], *, fail: bool = False) -> None:
        self.rows = rows
        self.fail = fail
        self.added: list[object] = []

    def scalars(self, statement: object) -> list[AuditEvent]:
        if self.fail:
            raise RuntimeError("database down")
        return sorted(self.rows, key=lambda row: (row.created_at, str(row.id)), reverse=True)

    def add(self, row: object) -> None:
        self.added.append(row)


def _client(session: _Rows) -> TestClient:
    app = create_app()

    def override():
        yield session

    app.dependency_overrides[get_db] = override
    return TestClient(app)


def _event(**overrides: object) -> AuditEvent:
    payload: dict[str, object] = {
        "symbol": "BTC-USD",
        "shares": 1,
        "binding_constraint": "risk",
        "execution_permitted": False,
        "order_submitted": False,
    }
    if "payload" in overrides:
        payload = overrides.pop("payload")  # type: ignore[assignment]
    values: dict[str, object] = {
        "id": uuid4(),
        "correlation_id": "risk-log-1",
        "action": "risk.size.recorded",
        "payload": payload,
        "created_at": datetime(2026, 11, 8, 16, 0, tzinfo=UTC),
    }
    values.update(overrides)
    return AuditEvent(**values)


def test_size_rows_are_listed_and_previews_stay_unlogged() -> None:
    session = _Rows([_event()])
    with _client(session) as client:
        response = client.get(PATH)
        again = client.get(PATH)
        posted = client.post(PATH)
        paths = client.app.openapi()["paths"]

    body = response.json()
    assert response.status_code == 200
    assert again.json() == body
    assert posted.status_code == 405
    assert body["persisted_action"] == "risk.size.recorded"
    assert body["shield_persisted"] is False
    assert body["reservation_persisted"] is False
    assert [item["kind"] for item in body["unlogged"]] == [
        "shield_preview",
        "reservation_preview",
    ]
    assert all(item["persisted"] is False for item in body["unlogged"])
    assert len(body["events"]) == 1
    assert body["events"][0]["action"] == "risk.size.recorded"
    assert body["events"][0]["order_submitted"] is False
    assert body["execution_permitted"] is False
    assert body["order_submitted"] is False
    assert body["source"] == "local_audit_log"
    assert session.added == []
    assert set(paths[PATH]) == {"get"}
    assert not any(path.endswith("/events") for path in paths)


def test_a_row_that_claims_an_order_hides_the_log() -> None:
    claimed = _event(
        payload={
            "symbol": "BTC-USD",
            "shares": 1,
            "binding_constraint": "risk",
            "execution_permitted": False,
            "order_submitted": True,
        }
    )
    with _client(_Rows([claimed])) as client:
        response = client.get(PATH)

    assert response.status_code == 503
    assert response.json() == {"detail": "Risk event log is unavailable."}
    assert "order_submitted" not in response.text or response.json()["detail"]


def test_a_down_database_hides_the_log() -> None:
    with _client(_Rows([], fail=True)) as client:
        response = client.get(PATH)

    assert response.status_code == 503
    assert response.json()["detail"] == "Risk event log is unavailable."
