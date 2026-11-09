"""Live-gate evidence. The route cannot submit, and it does not echo secrets."""

import os

from fastapi.testclient import TestClient

from veytrix_api.main import create_app
from veytrix_api.settings import Settings
from veytrix_quant.mac01.config import LIVE_CONFIRM_PHRASE, UnsafeConfiguration, load_config

PATH = "/api/v1/system/submission"


def _client() -> TestClient:
    settings = Settings(
        veytrix_env="local",
        veytrix_enable_live_broker=False,
        database_url="postgresql+psycopg://veytrix:local-dev-only@127.0.0.1:1/veytrix",
    )
    return TestClient(create_app(settings))


def test_shipped_config_cannot_submit_and_echoes_nothing(monkeypatch) -> None:
    monkeypatch.delenv("MAC01_LIVE_CONFIRM", raising=False)
    monkeypatch.setenv("ALPACA_PAPER_API_KEY", "pk-test-not-a-real-key")

    with _client() as client:
        response = client.get(PATH)
        again = client.get(PATH)
        posted = client.post(PATH)
        paths = client.app.openapi()["paths"]

    body = response.json()
    assert response.status_code == 200
    assert again.json() == body
    assert posted.status_code == 405
    assert body["config_valid"] is True
    assert body["config_mode"] == "paper"
    assert body["config_live_enabled"] is False
    assert body["config_submit_orders"] is False
    assert body["config_kill_switch"] is False
    assert body["expected_account_set"] is False
    assert [item["name"] for item in body["conditions"]] == [
        "mode_live",
        "live_enabled",
        "submit_orders",
        "confirm_phrase",
        "submit_flag",
        "account_match",
        "account_active",
        "kill_switch_off",
    ]
    assert body["conditions_met"] == 0
    assert all(item["met"] is False for item in body["conditions"])
    assert body["account_status"] == "not_read"
    assert body["ledger_kill_switch"] == "not_read"
    assert body["submit_flag"] is False
    assert body["api_reaches_engine"] is False
    assert body["broker_called"] is False
    assert body["paper_submission_from_api"] is False
    assert body["live_submission_possible"] is False
    assert body["expected_account_echoed"] is False
    assert body["confirm_phrase_echoed"] is False
    assert body["execution_permitted"] is False
    assert body["order_submitted"] is False
    assert body["order_route"] == "absent"
    assert "pk-test-not-a-real-key" not in response.text
    assert LIVE_CONFIRM_PHRASE not in response.text
    assert "order_id" not in body
    assert set(paths[PATH]) == {"get"}
    assert os.environ["ALPACA_PAPER_API_KEY"] == "pk-test-not-a-real-key"


def test_a_matching_phrase_and_a_live_config_still_cannot_submit(monkeypatch) -> None:
    shipped = load_config()
    live_looking = shipped.model_copy(
        update={
            "mode": "live",
            "live_enabled": True,
            "submit_orders": True,
            "kill_switch": False,
            "expected_account_number": "ACCT9",
        }
    )
    monkeypatch.setattr("veytrix_api.submission.load_config", lambda path=None: live_looking)
    monkeypatch.setenv("MAC01_LIVE_CONFIRM", LIVE_CONFIRM_PHRASE)

    with _client() as client:
        response = client.get(PATH)

    body = response.json()
    met = {item["name"]: item["met"] for item in body["conditions"]}
    assert response.status_code == 200
    assert met["mode_live"] is True
    assert met["live_enabled"] is True
    assert met["submit_orders"] is True
    assert met["confirm_phrase"] is True
    assert met["submit_flag"] is False
    assert met["account_match"] is False
    assert met["account_active"] is False
    assert met["kill_switch_off"] is False
    assert body["conditions_met"] == 4
    assert body["expected_account_set"] is True
    assert body["live_submission_possible"] is False
    assert body["paper_submission_from_api"] is False
    assert body["api_reaches_engine"] is False
    assert body["broker_called"] is False
    assert "ACCT9" not in response.text
    assert LIVE_CONFIRM_PHRASE not in response.text


def test_a_wrong_phrase_is_not_echoed(monkeypatch) -> None:
    monkeypatch.setenv("MAC01_LIVE_CONFIRM", "not-the-phrase")

    with _client() as client:
        response = client.get(PATH)

    body = response.json()
    confirm = next(item for item in body["conditions"] if item["name"] == "confirm_phrase")
    assert confirm["met"] is False
    assert "not-the-phrase" not in response.text
    assert body["live_submission_possible"] is False


def test_an_unsafe_config_meets_nothing(monkeypatch) -> None:
    def refuse(path=None):
        raise UnsafeConfiguration("refused")

    monkeypatch.delenv("MAC01_LIVE_CONFIRM", raising=False)
    monkeypatch.setattr("veytrix_api.submission.load_config", refuse)

    with _client() as client:
        response = client.get(PATH)

    body = response.json()
    assert body["config_valid"] is False
    assert body["config_mode"] is None
    assert body["expected_account_set"] is None
    assert body["conditions_met"] == 0
    assert body["live_submission_possible"] is False
    assert body["api_reaches_engine"] is False
