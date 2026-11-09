"""The shield preview route writes nothing and cannot submit."""

from fastapi.testclient import TestClient

from veytrix_api.main import create_app
from veytrix_api.settings import Settings

BODY = {
    "symbol": "AAPL",
    "side": "long",
    "limit_price": "40.00",
    "quantity": "1",
    "position_notional": "0.00",
    "orders_today": 1,
    "quote_age_seconds": 10,
    "leverage": "1",
}


def test_shield_preview_passes_the_rule_and_withholds_release() -> None:
    settings = Settings(
        veytrix_env="local",
        veytrix_enable_live_broker=False,
        database_url="postgresql+psycopg://veytrix:local-dev-only@127.0.0.1:1/veytrix",
    )
    with TestClient(create_app(settings)) as client:
        response = client.post("/api/v1/risk/shield/preview", json=BODY)
        again = client.post("/api/v1/risk/shield/preview", json=BODY)
        fetched = client.get("/api/v1/risk/shield/preview")

    body = response.json()
    assert response.status_code == 200
    assert again.json() == body
    assert fetched.status_code == 405
    assert body["rule_result"] == "pass"
    assert body["reasons"] == []
    assert body["notional"] == "40.00"
    assert body["release"] == "withheld"
    assert body["buying_power_checked"] is False
    assert body["owner_approved"] is False
    assert body["broker_reconciled"] is False
    assert body["execution_permitted"] is False
    assert body["order_submitted"] is False
    assert body["max_notional"] == "100.00"
    assert "cannot submit an order" in body["note"]


def test_shield_preview_rejects_a_number_and_a_short() -> None:
    settings = Settings(
        veytrix_env="local",
        veytrix_enable_live_broker=False,
        database_url="postgresql+psycopg://veytrix:local-dev-only@127.0.0.1:1/veytrix",
    )
    with TestClient(create_app(settings)) as client:
        numbered = client.post(
            "/api/v1/risk/shield/preview",
            json={**BODY, "limit_price": 40},
        )
        short = client.post("/api/v1/risk/shield/preview", json={**BODY, "side": "short"})

    assert numbered.status_code == 422
    assert short.status_code == 200
    assert short.json()["rule_result"] == "fail"
    assert short.json()["reasons"] == ["short"]
    assert short.json()["execution_permitted"] is False
    assert "order_id" not in short.json()
