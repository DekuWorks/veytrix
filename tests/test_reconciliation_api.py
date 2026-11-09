"""Local reconciliation. The broker side of every row stays unread."""

from datetime import UTC, datetime
from decimal import Decimal

from fastapi.testclient import TestClient

from veytrix_api.db import get_db
from veytrix_api.main import create_app
from veytrix_api.models import Mac01OrderRow
from veytrix_api.schemas import TERMINAL_ORDER_STATUSES
from veytrix_quant.mac01.ledger import TERMINAL_STATUSES

PATH = "/api/v1/ledger/reconciliation"


class _Orders:
    def __init__(self, rows: list[Mac01OrderRow], *, fail: bool = False) -> None:
        self.rows = rows
        self.fail = fail

    def scalars(self, statement: object) -> list[Mac01OrderRow]:
        if self.fail:
            raise RuntimeError("database down")
        return self.rows


def _client(session: _Orders) -> TestClient:
    app = create_app()

    def override():
        yield session

    app.dependency_overrides[get_db] = override
    return TestClient(app)


def _order(**overrides: object) -> Mac01OrderRow:
    values: dict[str, object] = {
        "client_order_id": "mac01-paper-1",
        "mode": "paper",
        "side": "buy",
        "status": "pending_submit",
        "broker_order_id": None,
        "filled_qty": Decimal("0"),
        "created_at": datetime(2026, 11, 8, 14, 35, tzinfo=UTC),
    }
    values.update(overrides)
    return Mac01OrderRow(**values)


def test_terminal_statuses_match_the_ledger() -> None:
    assert TERMINAL_ORDER_STATUSES == TERMINAL_STATUSES


def test_an_empty_ledger_is_not_reconciled() -> None:
    with _client(_Orders([])) as client:
        response = client.get(PATH)
        again = client.get(PATH)
        posted = client.post(PATH)
        paths = client.app.openapi()["paths"]

    body = response.json()
    assert response.status_code == 200
    assert again.json() == body
    assert posted.status_code == 405
    assert body["local_orders"] == 0
    assert body["local_fills"] == 0
    assert body["local_open"] == 0
    assert body["broker_rows_read"] == 0
    assert body["broker_read"] == "absent"
    assert body["alpaca_called"] is False
    assert body["reconciled"] is False
    assert body["rows"] == []
    assert body["execution_permitted"] is False
    assert body["order_submitted"] is False
    assert body["order_route"] == "absent"
    assert body["source"] == "local_ledger"
    assert "nothing here is reconciled" in body["note"]
    assert set(paths[PATH]) == {"get"}
    assert "/api/v1/broker/paper/account" not in paths


def test_a_stored_broker_id_is_still_not_a_match() -> None:
    pending = _order()
    filled = _order(
        client_order_id="mac01-paper-2",
        status="filled",
        broker_order_id="broker-id-2",
        filled_qty=Decimal("1.5"),
        created_at=datetime(2026, 11, 8, 15, 0, tzinfo=UTC),
    )
    with _client(_Orders([filled, pending])) as client:
        response = client.get(PATH)

    body = response.json()
    assert response.status_code == 200
    assert body["local_orders"] == 2
    assert body["local_fills"] == 1
    assert body["local_open"] == 1
    assert body["reconciled"] is False
    assert body["alpaca_called"] is False
    first = body["rows"][0]
    assert first["client_order_id"] == "mac01-paper-2"
    assert first["broker_order_id"] == "broker-id-2"
    assert first["broker_order_stored"] is True
    assert first["broker_status"] == "not_read"
    assert first["matched"] is False
    assert first["reason"] == "broker_not_read"
    assert body["rows"][1]["broker_order_stored"] is False
    assert body["rows"][1]["local_status"] == "pending_submit"


def test_an_unknown_status_hides_the_list() -> None:
    with _client(_Orders([_order(status="invented")])) as client:
        response = client.get(PATH)

    assert response.status_code == 503
    assert response.json() == {"detail": "Local reconciliation is unavailable."}


def test_a_down_database_hides_the_list() -> None:
    with _client(_Orders([], fail=True)) as client:
        response = client.get(PATH)

    assert response.status_code == 503
    assert response.json()["detail"] == "Local reconciliation is unavailable."
