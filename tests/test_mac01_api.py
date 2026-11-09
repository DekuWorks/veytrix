import ast
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from mac01_helpers import FakeBroker, broker_order, make_engine, sqlite_engine
from veytrix_api.db import get_db
from veytrix_api.main import create_app
from veytrix_quant.mac01.engine import client_order_id_for
from veytrix_quant.mac01.ledger import Ledger

pytestmark = pytest.mark.filterwarnings("ignore::sqlalchemy.exc.SAWarning")
ROOT = Path(__file__).resolve().parents[1]
BASE = "/api/v1/strategies/mac-01"


def _client(engine) -> TestClient:
    app = create_app()

    def override():
        session = Session(engine)
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override
    return TestClient(app)


def test_status_before_any_run_reports_no_data_and_paper_posture() -> None:
    engine = sqlite_engine()
    Ledger(engine).state()

    with _client(engine) as client:
        status = client.get(f"{BASE}/status").json()
        chart = client.get(f"{BASE}/chart").json()
        performance = client.get(f"{BASE}/performance").json()
        assert client.get(f"{BASE}/signals").json() == {"signals": []}
        assert client.get(f"{BASE}/orders").json() == {"orders": []}

    assert status["broker"] == "alpaca_trading_api"
    assert status["config_mode"] == "paper" and status["money"] == "paper"
    assert status["config_live_enabled"] is False
    assert status["config_expected_account_set"] is False
    assert status["order_route"] == "none"
    assert status["order_submitter"] == "cli_runner_only"
    assert status["config_valid"] is True
    assert status["config_submit_orders"] is False
    assert status["max_notional_per_trade"] == "100.00"
    assert status["max_position_notional"] == "100.00"
    assert status["max_orders_per_day"] == 2
    assert status["last_mode"] is None
    assert status["last_run_at"] is None
    assert "not investment advice" in status["disclaimer"]
    assert chart["available"] is False and chart["points"] == []
    assert performance["mode"] == "paper"
    assert performance["unrealised_available"] is False
    assert performance["unrealised_pl"] is None
    assert performance["realised_pl"] == "0"
    assert performance["filled_orders"] == 0


def test_status_is_503_when_the_ledger_is_missing() -> None:
    from sqlalchemy import create_engine

    empty = create_engine("sqlite://")
    with _client(empty) as client:
        response = client.get(f"{BASE}/status")

    assert response.status_code == 503
    assert response.json() == {"detail": "MAC-01 ledger is unavailable."}


def test_routes_report_ledger_rows_after_a_run() -> None:
    engine = sqlite_engine()
    broker = FakeBroker()
    make_engine(engine, broker).run()
    cid = client_order_id_for("paper", "mac-01.3", "AAPL", datetime(2026, 11, 6).date(), "BUY")
    broker.orders_by_client_id[cid] = broker_order(
        cid, status="filled", filled_qty="0.904977375", filled_avg_price="110.50"
    )
    make_engine(engine, broker).run()

    with _client(engine) as client:
        status = client.get(f"{BASE}/status").json()
        signals = client.get(f"{BASE}/signals").json()["signals"]
        orders = client.get(f"{BASE}/orders").json()["orders"]
        chart = client.get(f"{BASE}/chart").json()
        performance = client.get(f"{BASE}/performance").json()

    assert status["last_run_status"] == "ok" and status["last_mode"] == "paper"
    assert status["last_session_date"] == "2026-11-06"
    assert signals[0]["side"] == "BUY" and signals[0]["session_date"] == "2026-11-06"
    assert orders[0]["status"] == "filled" and orders[0]["mode"] == "paper"
    assert orders[0]["notional"] == "100.00" and orders[0]["qty"] is None
    assert orders[0]["filled_qty"] == "0.904977375"
    assert Decimal(orders[0]["filled_avg_price"]) == Decimal("110.50")
    assert chart["available"] is True
    assert len(chart["points"]) == 100
    assert chart["points"][-1]["close"] == "110"
    assert chart["points"][18]["sma_fast"] is None
    assert chart["points"][-1]["sma_slow"] is not None
    assert chart["markers"] == [{"session_date": "2026-11-06", "side": "BUY"}]
    assert performance["filled_orders"] == 1
    assert Decimal(performance["realised_pl"]) == 0
    assert performance["unrealised_available"] is True


def test_realised_pl_is_fifo_from_broker_fills_only() -> None:
    from veytrix_api.models import Mac01OrderRow
    from veytrix_api.routers.strategies import realised_pl

    def row(side: str, qty: str, price: str | None) -> Mac01OrderRow:
        return Mac01OrderRow(
            mode="paper",
            side=side,
            filled_qty=Decimal(qty),
            filled_avg_price=Decimal(price) if price else None,
        )

    pnl, filled = realised_pl(
        [row("buy", "1", "100"), row("sell", "1", "112.5"), row("buy", "0", None)]
    )
    assert pnl == Decimal("12.5") and filled == 2
    fractional, _ = realised_pl([row("buy", "0.5", "200"), row("sell", "0.5", "210")])
    assert fractional == Decimal("5.0")
    broken, _ = realised_pl([row("sell", "1", "100")])
    assert broken is None


def test_pause_resume_and_kill_switch_change_only_flags() -> None:
    engine = sqlite_engine()
    Ledger(engine).state()

    with _client(engine) as client:
        paused = client.post(f"{BASE}/pause").json()
        resumed = client.post(f"{BASE}/resume").json()
        killed = client.post(f"{BASE}/kill-switch").json()

    assert paused["paused"] is True
    assert resumed["paused"] is False
    assert killed["kill_switch"] is True
    assert Ledger(engine).state().kill_switch is True
    assert Ledger(engine).all_orders() == []


def test_no_api_route_can_submit_an_order() -> None:
    paths = create_app().openapi()["paths"]
    post_paths = {path for path, item in paths.items() if "post" in item}

    mac01_posts = {path for path in post_paths if "mac-01" in path}
    assert mac01_posts == {f"{BASE}/pause", f"{BASE}/resume", f"{BASE}/kill-switch"}
    for path in post_paths:
        assert "order" not in path.lower(), path
        assert "submit" not in path.lower(), path
    for path in paths:
        assert "submit" not in path.lower(), path


def test_api_package_does_not_import_a_broker_client_or_the_engine() -> None:
    banned = {
        "veytrix_quant.mac01.alpaca_trading",
        "veytrix_quant.mac01.alpaca_data",
        "veytrix_quant.mac01.ledger",
        "alpaca",
        "requests",
        "veytrix_quant.mac01.engine",
        "veytrix_quant.mac01.__main__",
        "httpx",
    }
    for path in (ROOT / "services" / "api" / "veytrix_api").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module not in banned, f"{path.name} imports {node.module}"
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name not in banned, f"{path.name} imports {alias.name}"


def test_status_timestamps_are_utc() -> None:
    engine = sqlite_engine()
    ledger = Ledger(engine, clock=lambda: datetime(2026, 11, 6, 21, 30, tzinfo=UTC))
    ledger.record_run("ok", "NO_ACTION: hold", datetime(2026, 11, 6).date())

    with _client(engine) as client:
        status = client.get(f"{BASE}/status").json()

    assert status["last_run_at"] == "2026-11-06T21:30:00Z"
    assert status["last_run_message"] == "NO_ACTION: hold"


def test_performance_ignores_orders_and_positions_from_the_other_mode() -> None:
    from veytrix_api.models import Mac01OrderRow

    engine = sqlite_engine()
    ledger = Ledger(engine, clock=lambda: datetime(2026, 11, 9, 15, 0, tzinfo=UTC))
    for index, (mode, side, price) in enumerate(
        [("live", "buy", "100"), ("live", "sell", "150"), ("paper", "buy", "100")]
    ):
        ledger.insert_pending_order(
            Mac01OrderRow(
                client_order_id=f"o-{index}",
                mode=mode,
                strategy_version="mac-01.3",
                symbol="AAPL",
                session_date=datetime(2026, 11, 6).date(),
                side=side,
                notional=Decimal("50.00") if side == "buy" else None,
                qty=Decimal("0.5") if side == "sell" else None,
                order_type="market",
                time_in_force="day",
                status="filled",
                filled_qty=Decimal("0.5"),
                filled_avg_price=Decimal(price),
            )
        )
    ledger.record_run("ok", "NO_ACTION: hold", None, "live")
    ledger.record_position(None)

    with _client(engine) as client:
        performance = client.get(f"{BASE}/performance").json()

    assert performance["mode"] == "paper"
    assert performance["filled_orders"] == 1 and Decimal(performance["realised_pl"]) == 0
    assert performance["unrealised_available"] is False
    assert performance["position_qty"] is None
