"""Event shapes stay off the API and cannot describe a live transfer."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from veytrix_api.events import CONTRACTS, EVENT_TYPES, DistributionProposed, OrderSubmitted
from veytrix_api.main import create_app


def test_event_contracts_cover_the_plan_and_are_not_routes() -> None:
    assert tuple(CONTRACTS) == EVENT_TYPES
    source = Path("services/api/veytrix_api/main.py").read_text(encoding="utf-8")
    assert "veytrix_api.events" not in source
    paths = create_app().openapi()["paths"]
    assert not any("distribution" in path or path.endswith("/events") for path in paths)
    order_paths = {path for path in paths if "order" in path}
    assert order_paths <= {
        "/api/v1/strategies/mac-01/orders",
        "/api/v1/paper-swaps/orders",
    }
    for path in order_paths:
        assert set(paths[path]) == {"get"}


def test_order_and_distribution_shapes_cannot_claim_execution() -> None:
    moment = datetime(2026, 11, 8, tzinfo=UTC)
    order = OrderSubmitted(
        occurred_at=moment,
        correlation_id="event-1",
        submitted_by="cli_runner_only",
        broker="alpaca_paper",
        symbol="AAPL",
        side="buy",
        client_order_id="mac01-1",
    )
    proposal = DistributionProposed(
        occurred_at=moment,
        correlation_id="event-1",
        amount="0.00",
        currency="USD",
    )
    assert order.live is False
    assert order.submitted_by == "cli_runner_only"
    assert proposal.transfer_executed is False
    with pytest.raises(ValidationError):
        OrderSubmitted(
            occurred_at=moment,
            correlation_id="event-1",
            submitted_by="cli_runner_only",
            live=True,
            broker="alpaca_paper",
            symbol="AAPL",
            side="buy",
            client_order_id="mac01-1",
        )
    with pytest.raises(ValidationError):
        DistributionProposed(
            occurred_at=moment,
            correlation_id="event-1",
            amount="10.00",
            currency="USD",
            transfer_executed=True,
        )
