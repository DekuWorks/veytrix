"""Classify public Coinbase tickers. A failed feed does not grow a substitute price."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

STALE_AFTER_SECONDS = 120
STALE_AFTER = timedelta(seconds=STALE_AFTER_SECONDS)

FeedStatus = Literal["up", "stale", "down"]
OverallStatus = Literal["ok", "degraded", "unavailable"]


def age_seconds(retrieved_at: datetime, now: datetime) -> int:
    moment = retrieved_at if retrieved_at.tzinfo is not None else retrieved_at.replace(tzinfo=UTC)
    elapsed = int((now.astimezone(UTC) - moment.astimezone(UTC)).total_seconds())
    return max(elapsed, 0)


def classify_feed(retrieved_at: datetime, now: datetime) -> FeedStatus:
    if age_seconds(retrieved_at, now) > STALE_AFTER_SECONDS:
        return "stale"
    return "up"


def overall_status(statuses: list[FeedStatus]) -> OverallStatus:
    if statuses and all(status == "up" for status in statuses):
        return "ok"
    if statuses and all(status == "down" for status in statuses):
        return "unavailable"
    return "degraded"
