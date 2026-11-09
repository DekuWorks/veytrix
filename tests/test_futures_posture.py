"""FUTURES-01 posture is local. The route does not call Topstep or a broker."""

from pathlib import Path

from fastapi.testclient import TestClient

from veytrix_api.main import create_app
from veytrix_api.settings import Settings

PATH = "/api/v1/futures/posture"
ROUTER = Path("services/api/veytrix_api/routers/futures.py")


def _client() -> TestClient:
    settings = Settings(
        veytrix_env="local",
        veytrix_enable_live_broker=False,
        database_url="postgresql+psycopg://veytrix:local-dev-only@127.0.0.1:1/veytrix",
    )
    return TestClient(create_app(settings))


def test_futures_posture_stays_disabled_without_a_broker() -> None:
    with _client() as client:
        response = client.get(PATH)
        again = client.get(PATH)
        posted = client.post(PATH)
        paths = client.app.openapi()["paths"]

    body = response.json()
    assert response.status_code == 200
    assert again.json() == body
    assert posted.status_code == 405
    assert body["desk"] == "FUTURES-01"
    assert body["status"] == "disabled"
    assert body["symbols"] == ["MES", "MNQ"]
    assert body["topstep_automation"] == "disabled"
    assert body["topstep_account"] == "not_connected"
    assert body["orders"] == "absent"
    assert body["market_data"] == "not_read"
    assert body["can_enable"] is False
    assert body["execution_permitted"] is False
    assert body["order_submitted"] is False
    assert body["broker_called"] is False
    assert body["source"] == "local_posture"
    assert "does not submit" in body["note"]
    assert set(paths[PATH]) == {"get"}
    assert "/api/v1/futures/orders" not in paths
    router = ROUTER.read_text(encoding="utf-8")
    assert "TradingClient" not in router
    assert "httpx" not in router
    assert "requests" not in router
