"""GET /api/v1/treasury/monthly-summary projects paper fills. It cannot pay."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from veytrix_api.db import get_db
from veytrix_api.main import create_app
from veytrix_api.routers import treasury as treasury_router
from veytrix_risk.treasury import project_month, review_date


def _fill(side: str, qty: str, price: str, mode: str = "paper") -> SimpleNamespace:
    return SimpleNamespace(
        side=side,
        filled_qty=Decimal(qty),
        filled_avg_price=Decimal(price),
        mode=mode,
    )


class _Orders:
    def __init__(self, rows: list[object], *, fail: bool = False) -> None:
        self.rows = rows
        self.fail = fail
        self.added: list[object] = []
        self.commits = 0

    def scalars(self, statement: object) -> list[object]:
        del statement
        if self.fail:
            raise RuntimeError("database down")
        return list(self.rows)

    def add(self, row: object) -> None:
        self.added.append(row)

    def commit(self) -> None:
        self.commits += 1


def _client(session: _Orders) -> tuple[object, TestClient]:
    app = create_app()

    def override():
        yield session

    app.dependency_overrides[get_db] = override
    return app, TestClient(app)


def test_monthly_summary_projects_paper_fills_and_cannot_post() -> None:
    rows = [
        _fill("buy", "1", "100"),
        _fill("sell", "1", "110"),
        _fill("buy", "1", "1", mode="live"),
    ]
    session = _Orders(rows)
    app, client = _client(session)
    with client:
        first = client.get("/api/v1/treasury/monthly-summary")
        second = client.get("/api/v1/treasury/monthly-summary")
        posted = client.post("/api/v1/treasury/monthly-summary")
        approved = client.post("/api/v1/treasury/distributions/1/approve")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    body = first.json()
    expected = project_month(realised_profit="10", costs="0", loss_carryforward="0")
    year, month = (int(part) for part in body["period"].split("-"))
    assert body["realised_profit"] == format(expected.realised_profit, "f")
    assert body["costs"] == "0.00"
    assert body["loss_carryforward"] == "0.00"
    assert body["eligible_profit"] == "10.00"
    assert body["proposed_distribution"] == "5.00"
    assert body["retained"] == "5.00"
    assert body["loss_carryforward_out"] == "0.00"
    assert body["distribution_fraction"] == "0.50"
    assert body["distribution_cap"] == "2000.00"
    assert body["review_on"] == review_date(year, month).isoformat()
    assert body["fills_counted"] == 2
    assert body["period_closed"] is False
    assert body["fees_included"] is False
    assert body["carryforward_stored"] is False
    assert body["broker_reconciled"] is False
    assert body["settled"] is False
    assert body["transfer_status"] == "not_attempted"
    assert body["approval_route"] == "absent"
    assert body["execution_permitted"] is False
    assert body["order_submitted"] is False
    assert body["transfer_submitted"] is False
    assert body["source"] == "local_projection"
    assert "broker" in body["note"]
    assert posted.status_code == 405
    assert approved.status_code == 404
    assert session.added == []
    assert session.commits == 0
    paths = app.openapi()["paths"]
    assert set(paths["/api/v1/treasury/monthly-summary"]) == {"get"}
    assert not any("approve" in path or "distribution" in path for path in paths)
    assert not any(path.endswith("/orders") and "broker" in path for path in paths)


def test_a_negative_paper_month_proposes_nothing() -> None:
    session = _Orders([_fill("buy", "1", "50"), _fill("sell", "1", "40")])
    _app, client = _client(session)
    with client:
        response = client.get("/api/v1/treasury/monthly-summary")
    assert response.status_code == 200
    body = response.json()
    assert body["eligible_profit"] == "-10.00"
    assert body["proposed_distribution"] == "0.00"
    assert body["loss_carryforward_out"] == "-10.00"
    assert body["transfer_submitted"] is False
    assert body["settled"] is False


def test_empty_ledger_is_a_zero_projection() -> None:
    _app, client = _client(_Orders([]))
    with client:
        response = client.get("/api/v1/treasury/monthly-summary")
    assert response.status_code == 200
    body = response.json()
    assert body["fills_counted"] == 0
    assert body["proposed_distribution"] == "0.00"
    assert body["eligible_profit"] == "0.00"
    assert body["broker_reconciled"] is False


def test_a_broken_ledger_live_mode_or_a_down_database_hides_the_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broken = _Orders([_fill("sell", "1", "40")])
    _app, client = _client(broken)
    with client:
        unavailable = client.get("/api/v1/treasury/monthly-summary")
    assert unavailable.status_code == 503

    down = _Orders([], fail=True)
    _app, client = _client(down)
    with client:
        failed = client.get("/api/v1/treasury/monthly-summary")
    assert failed.status_code == 503

    monkeypatch.setattr(
        treasury_router,
        "load_config",
        lambda: SimpleNamespace(mode="live"),
    )
    _app, client = _client(_Orders([_fill("buy", "1", "10"), _fill("sell", "1", "12")]))
    with client:
        live = client.get("/api/v1/treasury/monthly-summary")
    assert live.status_code == 503
