"""Process-local token bucket.

This is not a distributed limit. A second API process, or a restart, starts
with a full bucket. One client key shares one bucket, so a tight loop cannot
fan out across paths and stampede Coinbase.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from threading import Lock

# One loopback desk. Overview (3 tickers / 2s) + Market (ticker / 2s, candles / 45s)
# + Quant + Events is about 130 requests/minute. 360/minute leaves room for another
# ticker page. Burst 24 is one Market load (ticker, 1-minute, daily) plus the same
# three on a product switch, with spare for a strict-mode remount. A faster loop
# empties the burst and then receives 429.
LOOPBACK_SUSTAINED_PER_MINUTE = 360
LOOPBACK_BURST = 24


class ProcessLocalRateLimiter:
    def __init__(
        self,
        limit: int,
        window_seconds: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
        burst: int | None = None,
    ) -> None:
        if limit < 1:
            raise ValueError("Rate limit must be at least 1.")
        if window_seconds <= 0:
            raise ValueError("Rate limit window must be positive.")
        chosen_burst = LOOPBACK_BURST if burst is None else burst
        if chosen_burst < 1:
            raise ValueError("Rate limit burst must be at least 1.")
        self.limit = limit
        self.window_seconds = window_seconds
        # A configured limit below the desk burst still rejects the next request.
        self.burst = min(chosen_burst, limit)
        self._refill_per_second = limit / window_seconds
        self._clock = clock
        self._buckets: dict[str, tuple[float, float]] = {}
        self._lock = Lock()

    def check(self, key: str) -> tuple[bool, int]:
        now = self._clock()
        with self._lock:
            tokens, updated = self._buckets.get(key, (float(self.burst), now))
            elapsed = now - updated
            if elapsed > 0:
                tokens = min(float(self.burst), tokens + elapsed * self._refill_per_second)
                updated = now
            if tokens < 1:
                self._buckets[key] = (tokens, updated)
                return False, 0
            tokens -= 1
            self._buckets[key] = (tokens, updated)
            return True, int(tokens)
