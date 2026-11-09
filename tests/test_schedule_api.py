"""The MAC-01 schedule route reports a stopped clock. It does not start a run."""

from fastapi.testclient import TestClient

from veytrix_api.main import create_app
from veytrix_api.settings import Settings
from veytrix_quant.mac01.config import UnsafeConfiguration, load_config
from veytrix_quant.mac01.schedule import RUN_DELAY_AFTER_OPEN


def _client() -> TestClient:
    settings = Settings(
        veytrix_env="local",
        veytrix_enable_live_broker=False,
        database_url="postgresql+psycopg://veytrix:local-dev-only@127.0.0.1:1/veytrix",
    )
    return TestClient(create_app(settings))


def test_schedule_status_does_not_start_and_does_not_read_a_calendar() -> None:
    with _client() as client:
        response = client.get("/api/v1/strategies/mac-01/schedule")
        again = client.get("/api/v1/strategies/mac-01/schedule")
        posted = client.post("/api/v1/strategies/mac-01/schedule")
        started = client.post("/api/v1/strategies/mac-01/schedule/start")
        paths = client.app.openapi()["paths"]

    body = response.json()
    assert response.status_code == 200
    assert again.json() == body
    assert posted.status_code == 405
    assert started.status_code == 404
    assert body["strategy"] == "mac-01"
    assert body["timezone"] == "America/New_York"
    assert body["run_clock"] == "09:35"
    assert body["delay_after_open_minutes"] == 5
    assert body["delay_after_open_minutes"] == int(RUN_DELAY_AFTER_OPEN.total_seconds() // 60)
    assert body["calendar"] == "not_read"
    assert body["next_session"] == "unknown"
    assert body["running"] is False
    assert body["process"] == "absent"
    assert body["submit_flag"] is False
    assert body["can_start"] is False
    assert body["config_valid"] is True
    assert body["config_mode"] == "paper"
    assert body["config_submit_orders"] is False
    assert body["config_live_enabled"] is False
    assert body["alpaca_called"] is False
    assert body["execution_permitted"] is False
    assert body["order_submitted"] is False
    assert body["order_route"] == "absent"
    assert body["source"] == "local_config"
    assert "does not start the scheduler" in body["note"]
    assert "order_id" not in body
    assert set(paths["/api/v1/strategies/mac-01/schedule"]) == {"get"}


def test_a_live_looking_config_still_cannot_start(monkeypatch) -> None:
    shipped = load_config()
    live_looking = shipped.model_copy(
        update={
            "mode": "live",
            "live_enabled": True,
            "submit_orders": True,
            "expected_account_number": "PAPERACCT",
        }
    )
    monkeypatch.setattr(
        "veytrix_api.routers.strategies.load_config", lambda path=None: live_looking
    )

    with _client() as client:
        response = client.get("/api/v1/strategies/mac-01/schedule")

    body = response.json()
    assert response.status_code == 200
    assert body["config_mode"] == "live"
    assert body["config_submit_orders"] is True
    assert body["config_live_enabled"] is True
    assert body["submit_flag"] is False
    assert body["can_start"] is False
    assert body["running"] is False
    assert body["alpaca_called"] is False
    assert body["execution_permitted"] is False
    assert body["order_submitted"] is False


def test_an_unsafe_config_still_cannot_start(monkeypatch) -> None:
    def refuse(path=None):
        raise UnsafeConfiguration("refused")

    monkeypatch.setattr("veytrix_api.routers.strategies.load_config", refuse)

    with _client() as client:
        response = client.get("/api/v1/strategies/mac-01/schedule")

    body = response.json()
    assert response.status_code == 200
    assert body["config_valid"] is False
    assert body["config_mode"] is None
    assert body["config_submit_orders"] is None
    assert body["can_start"] is False
    assert body["running"] is False
    assert body["alpaca_called"] is False
