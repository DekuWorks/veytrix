"""Roads does not pretend to be Claude when no key is configured."""

import pytest

from veytrix_api.claude_provider import reset
from veytrix_api.comms import safety
from veytrix_api.comms.replies import compose_reply


@pytest.fixture(autouse=True)
def _no_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    reset()


def test_roads_greeting_is_offline_and_not_model_generated() -> None:
    reply = compose_reply(None, "SUPERVISOR-01", "Hello Roads", history=[])  # type: ignore[arg-type]

    assert safety.LIVE_EXECUTION_ENABLED is False
    assert reply.origin != "model_generated"
    assert reply.origin == "scripted"
    assert "Claude is offline" in reply.content
    assert "No order is sent." in reply.content
    assert reply.meta["model"] == "disconnected"
