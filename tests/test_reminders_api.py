"""Reminder dates are local. The route creates no meeting and pays nothing."""

from fastapi.testclient import TestClient

from veytrix_api.main import create_app
from veytrix_api.settings import Settings


def _client() -> TestClient:
    settings = Settings(
        veytrix_env="local",
        veytrix_enable_live_broker=False,
        database_url="postgresql+psycopg://veytrix:local-dev-only@127.0.0.1:1/veytrix",
    )
    return TestClient(create_app(settings))


def test_reminder_dates_are_local_and_create_no_event() -> None:
    with _client() as client:
        response = client.get("/api/v1/treasury/reminders", params={"year": 2026, "month": 11})
        again = client.get("/api/v1/treasury/reminders", params={"year": 2026, "month": 11})
        posted = client.post("/api/v1/treasury/reminders", json={"year": 2026, "month": 11})
        meeting = client.post("/api/v1/meetings", json={"time": "09:00"})
        missing = client.get("/api/v1/treasury/reminders")
        paths = client.app.openapi()["paths"]

    body = response.json()
    assert response.status_code == 200
    assert again.json() == body
    assert posted.status_code == 405
    assert meeting.status_code == 404
    assert missing.status_code == 422
    assert body["period"] == "2026-11"
    assert body["accounting_close_on"] == "2026-12-01"
    assert body["accounting_close_shifted_for_weekend"] is False
    assert body["payout_review_on"] == "2026-12-07"
    assert body["payout_review_shifted_for_weekend"] is True
    assert body["meeting_time"] == "unconfirmed"
    assert body["daypilot"] == "absent"
    assert body["event_created"] is False
    assert body["transfer_submitted"] is False
    assert body["execution_permitted"] is False
    assert body["order_submitted"] is False
    assert body["source"] == "local_calendar"
    assert "No DayPilot event was created" in body["note"]
    assert "order_id" not in body
    assert set(paths["/api/v1/treasury/reminders"]) == {"get"}
    assert "/api/v1/meetings" not in paths
    assert not any("approve" in path or "distribution" in path for path in paths)
