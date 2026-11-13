"""Paper desk cycles against a scratch database on the Veytrix port, never 5432."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from comms_helpers import scratch_database
from veytrix_api.desks import cycle_desks
from veytrix_api.main import create_app
from veytrix_api.models import Mac01OrderRow, PaperFillRow, ResearchTaskRow
from veytrix_api.settings import Settings


@pytest.fixture(scope="module")
def database_url() -> str:
    return scratch_database("veytrix_desk_test")


def _settings(url: str) -> Settings:
    return Settings(
        veytrix_env="local",
        veytrix_enable_live_broker=False,
        database_url=url,
        rate_limit_per_minute=10_000,
    )


@pytest.fixture()
def db(database_url: str):
    app = create_app(_settings(database_url))
    session = Session(app.state.engine)
    try:
        yield session
    finally:
        session.close()
        app.state.engine.dispose()


@pytest.fixture()
def client(database_url: str):
    app = create_app(_settings(database_url))
    with TestClient(app) as test_client:
        yield test_client
    app.state.engine.dispose()


def _candles(start: datetime) -> list[tuple[datetime, Decimal]]:
    return [
        (start - timedelta(days=1), Decimal("100")),
        (start, Decimal("101")),
    ]


def test_crypto_fill_is_written_once_and_other_desks_stay_honest(db: Session) -> None:
    start = datetime(2026, 11, 13, tzinfo=UTC)
    cycle_desks(db, fetch=lambda: _candles(start), worker_id="test", now=start + timedelta(hours=1))
    db.commit()
    cycle_desks(db, fetch=lambda: _candles(start), worker_id="test", now=start + timedelta(hours=1))
    db.commit()

    fills = list(db.scalars(select(PaperFillRow)))
    assert len(fills) == 1
    assert fills[0].symbol == "BTC-USD"
    assert fills[0].price == Decimal("101")
    assert fills[0].execution_permitted is False
    assert fills[0].order_submitted is False
    assert fills[0].source_id == "coinbase-exchange"
    assert db.scalar(select(func.count()).select_from(Mac01OrderRow)) == 0

    from veytrix_api.models import DeskRunRow

    by_code = {row.agent_code: row for row in db.scalars(select(DeskRunRow))}
    assert by_code["CRYPTO-01"].state == "active"
    assert by_code["CRYPTO-01"].source_id == "coinbase-exchange"
    assert by_code["STOCK-01"].state == "idle"
    assert by_code["STOCK-01"].source_id == "synthetic-sample"
    assert by_code["ETF-01"].state == "idle"
    assert by_code["FUTURES-01"].state == "blocked"
    assert by_code["DEFI-01"].state == "blocked"
    for code in ("YIELD", "NFT", "TAX-LIEN", "LAND"):
        assert by_code[code].state == "blocked"
        assert by_code[code].block_reason == "no_provider"


def test_coinbase_failure_does_not_invent_a_fill(db: Session) -> None:
    def boom() -> list[tuple[datetime, Decimal]]:
        raise RuntimeError("coinbase down")

    before = db.scalar(select(func.count()).select_from(PaperFillRow))
    cycle_desks(db, fetch=boom, worker_id="test", now=datetime(2026, 11, 13, tzinfo=UTC))
    db.commit()
    from veytrix_api.models import DeskRunRow

    crypto = db.get(DeskRunRow, "CRYPTO-01")
    assert crypto is not None
    assert crypto.state == "failed"
    assert crypto.block_reason == "coinbase_unavailable"
    assert db.scalar(select(func.count()).select_from(PaperFillRow)) == before


def test_acknowledging_an_alert_leaves_the_task_blocked(db: Session, client: TestClient) -> None:
    now = datetime(2026, 11, 13, tzinfo=UTC)
    task = ResearchTaskRow(
        id=uuid.uuid4(),
        assignee_code="RESEARCH-01",
        assigned_by="SUPERVISOR-01",
        subject="NVIDIA",
        instruction="Read the stored note.",
        status="blocked",
        kind="research",
        blocked_reason="no_stored_source",
        created_at=now,
        updated_at=now,
    )
    db.add(task)
    db.commit()
    response = client.post(f"/api/v1/desks/alerts/{task.id}/ack")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "blocked"
    assert body["acknowledged"] is True
    assert body["execution_permitted"] is False
    assert body["order_submitted"] is False
    db.refresh(task)
    assert task.status == "blocked"
