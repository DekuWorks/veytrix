"""Paper webhook recorders reject the broker and do not call one."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from veytrix_execution.boundary import BoundaryError, PaperBoundary, RouteConflict
from veytrix_execution.cli_guard import PAPER_EXAMPLES, review_command, review_environment

ROOT = Path(__file__).resolve().parents[1]
EXECUTION = ROOT / "services" / "execution"
T0 = datetime(2026, 11, 13, 15, 0, tzinfo=UTC)


def desk() -> PaperBoundary:
    return PaperBoundary.from_mapping({})


def send(
    boundary: PaperBoundary,
    route: str,
    payload: object,
    key: str = "sig-1",
    *,
    retry: bool = False,
    seconds: float = 0,
    content_type: str | None = "application/json",
    strategy_id: str = "swing",
    account_ref: str = "paper-a",
):
    return boundary.ingest(
        route=route,
        strategy_id=strategy_id,
        account_ref=account_ref,
        idempotency_key=key,
        payload=payload,
        content_type=content_type,
        started_at=T0,
        now=T0 + timedelta(seconds=seconds),
        retry=retry,
    )


def test_defaults_are_none_and_recording_is_off() -> None:
    boundary = desk()

    assert boundary.mode == "paper"
    assert boundary.recording_enabled is False
    assert boundary.selected("swing", "paper-a") == "none"
    assert boundary.live_blocked is False


def test_one_route_per_strategy_and_account() -> None:
    boundary = desk()

    assert boundary.select("swing", "paper-a", "traderspost") == "traderspost"
    with pytest.raises(RouteConflict):
        boundary.select("swing", "paper-a", "signalstack")
    assert boundary.selected("swing", "paper-a") == "traderspost"

    with pytest.raises(RouteConflict):
        boundary.select("swing", "paper-b", "signalstack")
    with pytest.raises(RouteConflict):
        boundary.select("other", "paper-a", "tradingview_recorder")

    boundary.select("swing", "paper-a", "none")
    assert boundary.select("other", "paper-b", "signalstack") == "signalstack"
    assert boundary.selected("swing", "paper-a") == "none"


def test_replace_switches_the_same_pair_only() -> None:
    boundary = desk()
    boundary.select("swing", "paper-a", "traderspost")
    boundary.select("other", "paper-b", "signalstack")

    assert boundary.select("swing", "paper-a", "tradingview_recorder", replace=True) == (
        "tradingview_recorder"
    )
    assert boundary.selected("other", "paper-b") == "signalstack"


def test_traderspost_valid_payload_is_rejected_while_disabled() -> None:
    boundary = desk()
    receipt = send(boundary, "traderspost", {"ticker": "AMD", "action": "buy"})

    assert receipt.stored is True
    assert receipt.broker_outcome == "rejected"
    assert receipt.forwarded is False
    assert receipt.execution_permitted is False
    assert receipt.order_submitted is False
    assert receipt.response_body["messageCode"] == "route-disabled"
    assert receipt.response_body["quote"] is None
    assert receipt.row is not None
    assert receipt.row.mode == "paper"
    assert "mode=paper" in boundary.log_line(receipt.row)
    assert "broker_outcome=rejected" in boundary.log_line(receipt.row)


def test_traderspost_invalid_malformed_and_batch_payloads() -> None:
    boundary = desk()

    missing = send(boundary, "traderspost", {"ticker": "AMD"}, key="missing")
    malformed = send(boundary, "traderspost", "{", key="bad-json")
    batch = send(
        boundary,
        "traderspost",
        [{"ticker": "AMD", "action": "buy"}, {"ticker": "NVDA", "action": "sell"}],
        key="batch",
    )
    resize = send(boundary, "traderspost", {"ticker": "AMD", "action": "resize"}, key="resize")

    assert missing.response_body["messageCode"] == "invalid-payload"
    assert malformed.response_body["messageCode"] == "malformed-json"
    assert batch.response_body["messageCode"] == "batch-signals-not-enabled"
    assert resize.response_body["messageCode"] == "resize-requires-quantity"
    assert all(item.forwarded is False for item in (missing, malformed, batch, resize))


def test_traderspost_over_budget_is_not_stored() -> None:
    boundary = desk()
    payload = {f"k{index}": 1 for index in range(700)}
    payload["ticker"] = "AMD"
    payload["action"] = "buy"

    receipt = send(boundary, "traderspost", payload, key="wide")

    assert receipt.stored is False
    assert receipt.row is None
    assert receipt.response_body["messageCode"] == "payload-budget-exceeded"
    assert receipt.response_body["audit_id"] is None
    assert boundary.audit.rows == []


def test_duplicate_and_retry_do_not_create_a_second_order() -> None:
    boundary = desk()
    payload = {"ticker": "AMD", "action": "buy", "signalPrice": 143.12, "password": "hunter2"}
    first = send(boundary, "traderspost", payload, key="same")
    duplicate = send(boundary, "traderspost", payload, key="same")
    retried = send(boundary, "traderspost", payload, key="same", retry=True)

    assert first.row is not None
    assert duplicate.duplicate is True
    assert duplicate.stored is False
    assert duplicate.response_body["audit_id"] == first.row.audit_id
    assert retried.row is first.row
    assert retried.row is not None
    assert retried.row.retry_count == 1
    assert len(boundary.audit.rows) == 1
    assert first.row.signal["sender"]["password"] == "[redacted]"
    assert "hunter2" not in str(first.row.signal)
    assert "143.12" not in boundary.log_line(first.row)
    assert first.row.mode == "paper"


def test_timeout_rejects_before_a_broker_outcome_changes() -> None:
    boundary = desk()
    boundary.select("swing", "paper-a", "traderspost")
    boundary.enable_recording()

    receipt = send(
        boundary,
        "traderspost",
        {"ticker": "AMD", "action": "buy"},
        key="late",
        seconds=4,
    )

    assert receipt.row is not None
    assert receipt.row.timed_out is True
    assert receipt.response_body["messageCode"] == "timeout"
    assert receipt.broker_outcome == "rejected"
    assert receipt.forwarded is False


def test_enabled_paper_route_still_rejects_the_broker() -> None:
    boundary = desk()
    boundary.select("swing", "paper-a", "signalstack")
    boundary.enable_recording()

    receipt = send(
        boundary,
        "signalstack",
        {"symbol": "AAPL", "action": "buy", "quantity": 123},
    )

    assert receipt.response_body["messageCode"] == "broker-forwarding-disabled"
    assert receipt.row is not None
    assert receipt.row.broker_outcome == "rejected"
    assert receipt.row.forwarded is False
    assert receipt.row.order_submitted is False
    assert "mode=paper" in boundary.log_line(receipt.row)


def test_signalstack_invalid_payload_and_omitted_quantity() -> None:
    boundary = desk()
    boundary.select("swing", "paper-a", "signalstack")
    boundary.enable_recording()

    invalid = send(boundary, "signalstack", {"symbol": "AAPL"}, key="no-action")
    omitted = send(boundary, "signalstack", {"symbol": "AAPL", "action": "close"}, key="close")
    zero = send(
        boundary,
        "signalstack",
        {"symbol": "AAPL", "action": "buy", "quantity": 0},
        key="zero",
    )

    assert invalid.response_body["messageCode"] == "invalid-action"
    assert omitted.row is not None
    assert omitted.row.signal["quantity_omitted"] is True
    assert omitted.row.signal["quantity_defaulted"] is False
    assert omitted.row.signal["sender"] == {"symbol": "AAPL", "action": "close"}
    assert zero.response_body["messageCode"] == "invalid-quantity"


def test_signalstack_duplicate_retry_and_timeout() -> None:
    boundary = desk()
    payload = {"symbol": "AAPL", "action": "sell", "quantity": 123, "limit_price": 123.98}
    first = send(boundary, "signalstack", payload, key="ss-1")
    second = send(boundary, "signalstack", payload, key="ss-1")
    third = send(boundary, "signalstack", payload, key="ss-1", retry=True)
    late = send(boundary, "signalstack", payload, key="ss-late", seconds=3.1)

    assert first.broker_outcome == "rejected"
    assert second.duplicate is True
    assert third.row is not None and third.row.retry_count == 1
    assert late.response_body["messageCode"] == "timeout"
    assert len(boundary.audit.rows) == 2
    assert first.row is not None
    assert first.response_body["quote"] is None


def test_tradingview_message_is_not_an_order() -> None:
    boundary = desk()
    plain = send(
        boundary,
        "tradingview_recorder",
        "sender alert text",
        key="tv-text",
        content_type="text/plain",
    )
    shaped = send(
        boundary,
        "tradingview_recorder",
        {"ticker": "AAPL", "action": "buy"},
        key="tv-json",
        content_type="application/json",
    )

    assert plain.row is not None and shaped.row is not None
    assert plain.row.signal["interpreted_as_order"] is False
    assert plain.row.signal["quote"] is None
    assert shaped.row.signal["interpreted_as_order"] is False
    assert shaped.response_body["messageCode"] == "route-disabled"
    assert plain.forwarded is False and shaped.forwarded is False


def test_sender_cannot_flip_the_row_to_live() -> None:
    boundary = desk()
    receipt = send(
        boundary,
        "traderspost",
        {"ticker": "AMD", "action": "buy", "mode": "live"},
        key="claims-live",
    )

    assert receipt.row is not None
    assert receipt.row.mode == "paper"
    assert boundary.mode == "paper"


def test_live_variable_refuses_recording_without_keeping_the_value() -> None:
    boundary = PaperBoundary.from_mapping(
        {"ALPACA_LIVE_TRADE": "true", "ALPACA_API_KEY": "short-key"}
    )

    with pytest.raises(BoundaryError, match="ALPACA_LIVE_TRADE"):
        boundary.enable_recording()
    receipt = send(boundary, "traderspost", {"ticker": "AMD", "action": "buy"})

    assert boundary.recording_enabled is False
    assert receipt.response_body["messageCode"] == "live-environment-refused"
    assert "short-key" not in repr(boundary)
    assert receipt.forwarded is False


def test_process_environ_records_names_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAC01_LIVE_CONFIRM", "armed")
    monkeypatch.setenv("ALPACA_API_KEY", "short-key")

    boundary = PaperBoundary.from_process_environ()

    assert "MAC01_LIVE_CONFIRM" in boundary.live_names
    assert "armed" not in repr(boundary)
    assert "short-key" not in repr(boundary)


def test_cli_checklist_allows_paper_examples_and_runs_nothing() -> None:
    for example in PAPER_EXAMPLES:
        result = review_command(list(example))
        assert result.allowed is True
        assert result.executed is False

    refused = [
        [
            "alpaca",
            "order",
            "submit",
            "--symbol",
            "AAPL",
            "--side",
            "buy",
            "--qty",
            "1",
            "--type",
            "market",
        ],
        [
            "alpaca",
            "order",
            "submit",
            "--symbol",
            "AAPL",
            "--side",
            "buy",
            "--qty",
            "1",
            "--type",
            "market",
            "--dry-run",
            "--live",
        ],
        ["alpaca", "position", "close-all"],
        ["alpaca", "api", "POST", "/v2/orders"],
        ["alpaca", "account", "get", "|", "cat"],
        ["/usr/bin/alpaca", "account", "get"],
    ]
    for argv in refused:
        result = review_command(argv)
        assert result.allowed is False
        assert result.executed is False

    live = review_environment({"ALPACA_LIVE_TRADE": "true", "ALPACA_API_KEY": "short-key"})
    quiet = review_environment({"ALPACA_API_KEY": "short-key"})
    assert live.allowed is False and live.executed is False
    assert quiet.allowed is True
    assert "short-key" not in live.message
    assert "short-key" not in quiet.message


def test_execution_package_has_no_broker_client() -> None:
    banned = (
        "subprocess",
        "urlopen",
        "import httpx",
        "alpaca.markets",
        "veytrix_quant",
        "Mac01Engine",
        "import socket",
        "from socket",
    )
    sources = list(EXECUTION.rglob("*.py"))
    assert sources
    for path in sources:
        text = path.read_text(encoding="utf-8")
        folded = text.lower()
        for word in banned:
            assert word.lower() not in folded, f"{path.name} contains {word}"

    api = ROOT / "services" / "api"
    for path in api.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "veytrix_execution" not in text
        assert "grok_assistant" not in text
