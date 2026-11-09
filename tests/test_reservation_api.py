"""The reservation preview route writes nothing and cannot submit."""

from fastapi.testclient import TestClient

from veytrix_api.main import create_app
from veytrix_api.routers import risk as risk_router
from veytrix_api.settings import Settings

BODY = {
    "agent": "STOCK-01",
    "notional": "40.00",
    "idempotency_key": "stock-40",
    "outstanding": [{"agent": "DAY-01", "notional": "60.00", "idempotency_key": "day-60"}],
}


def _client() -> TestClient:
    settings = Settings(
        veytrix_env="local",
        veytrix_enable_live_broker=False,
        database_url="postgresql+psycopg://veytrix:local-dev-only@127.0.0.1:1/veytrix",
    )
    return TestClient(create_app(settings))


def test_reservation_preview_passes_and_withholds_release(monkeypatch) -> None:
    def fail_size(*_args, **_kwargs):
        raise AssertionError("reservation preview must not size a position")

    monkeypatch.setattr(risk_router, "size_position", fail_size)
    with _client() as client:
        response = client.post("/api/v1/risk/reservations/preview", json=BODY)
        again = client.post("/api/v1/risk/reservations/preview", json=BODY)
        fetched = client.get("/api/v1/risk/reservations/preview")

    body = response.json()
    assert response.status_code == 200
    assert again.json() == body
    assert fetched.status_code == 405
    assert body["rule_result"] == "pass"
    assert body["reasons"] == []
    assert body["requested"] == "40.00"
    assert body["reserved_before"] == "60.00"
    assert body["reserved_after"] == "100.00"
    assert body["book_cap"] == "100.00"
    assert body["release"] == "withheld"
    assert body["persisted"] is False
    assert body["lock"] == "absent"
    assert body["buying_power_checked"] is False
    assert body["broker_reconciled"] is False
    assert body["owner_approved"] is False
    assert body["execution_permitted"] is False
    assert body["order_submitted"] is False
    assert "cannot submit an order" in body["note"]
    assert "order_id" not in body


def test_reservation_preview_rejects_a_number_and_an_over_book() -> None:
    with _client() as client:
        numbered = client.post(
            "/api/v1/risk/reservations/preview",
            json={**BODY, "notional": 40},
        )
        extra = client.post(
            "/api/v1/risk/reservations/preview",
            json={**BODY, "buying_power": "100.00"},
        )
        over = client.post(
            "/api/v1/risk/reservations/preview",
            json={**BODY, "notional": "40.01"},
        )
        paths = client.app.openapi()["paths"]

    assert numbered.status_code == 422
    assert extra.status_code == 422
    assert over.status_code == 200
    assert over.json()["rule_result"] == "fail"
    assert over.json()["reasons"] == ["book"]
    assert over.json()["reserved_after"] == "60.00"
    assert over.json()["execution_permitted"] is False
    assert "order_id" not in over.json()
    assert set(paths["/api/v1/risk/reservations/preview"]) == {"post"}
    assert not any("approve" in path or "distribution" in path for path in paths)
