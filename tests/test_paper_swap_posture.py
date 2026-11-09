"""Paper-swap posture is local. The route does not record a swap."""

from pathlib import Path

from fastapi.testclient import TestClient

from veytrix_api.main import create_app
from veytrix_api.settings import Settings

PATH = "/api/v1/paper-swaps/posture"
ROUTER = Path("services/api/veytrix_api/routers/paper_swaps.py")


def _client() -> TestClient:
    settings = Settings(
        veytrix_env="local",
        veytrix_enable_live_broker=False,
        database_url="postgresql+psycopg://veytrix:local-dev-only@127.0.0.1:1/veytrix",
    )
    return TestClient(create_app(settings))


def test_posture_refuses_signing_without_the_ledger() -> None:
    with _client() as client:
        response = client.get(PATH)
        again = client.get(PATH)
        posted = client.post(PATH)
        paths = client.app.openapi()["paths"]

    body = response.json()
    assert response.status_code == 200
    assert again.json() == body
    assert posted.status_code == 405
    assert body["signing"] == "absent"
    assert body["broadcast"] == "absent"
    assert body["private_key"] == "refused"
    assert body["api_can_record"] is False
    assert body["mainnet"] == "refused"
    assert body["networks"] == ["solana-devnet", "sepolia", "base-sepolia"]
    assert body["chain_ids"] == ["devnet", "11155111", "84532"]
    assert body["executable"] is False
    assert body["execution_permitted"] is False
    assert body["order_submitted"] is False
    assert body["source"] == "local_posture"
    assert "does not sign" in body["note"]
    assert set(paths[PATH]) == {"get"}
    assert set(paths["/api/v1/paper-swaps/orders"]) == {"get"}
    router = ROUTER.read_text(encoding="utf-8")
    assert "veytrix_ai" not in router
    assert "eth_account" not in router
