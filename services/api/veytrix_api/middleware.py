"""Correlation ids and the process-local rate limit."""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from collections.abc import Callable

from veytrix_api.logging_config import correlation_id_var
from veytrix_api.ratelimit import ProcessLocalRateLimiter

_CORRELATION_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
logger = logging.getLogger("veytrix")


def correlation_id_from_headers(headers: list[tuple[bytes, bytes]]) -> str:
    for name, value in headers:
        if name.lower() == b"x-correlation-id":
            text = value.decode("latin-1", errors="ignore").strip()
            if _CORRELATION_ID.fullmatch(text):
                return text
            break
    return str(uuid.uuid4())


class CorrelationMiddleware:
    def __init__(self, app: Callable) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        correlation_id = correlation_id_from_headers(list(scope.get("headers", [])))
        token = correlation_id_var.set(correlation_id)
        status_code = 500
        started = time.perf_counter()

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                headers = list(message.get("headers", []))
                headers.append((b"x-correlation-id", correlation_id.encode("ascii")))
                headers.append((b"x-content-type-options", b"nosniff"))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            logger.info(
                "request",
                extra={
                    "http_method": scope.get("method"),
                    "path": scope.get("path"),
                    "status_code": status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                },
            )
            correlation_id_var.reset(token)


class RateLimitMiddleware:
    """Counts requests in this process. `/api/v1/health` is exempt so a probe can stay cheap."""

    def __init__(self, app: Callable, limiter: ProcessLocalRateLimiter) -> None:
        self.app = app
        self.limiter = limiter

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http" or scope.get("path") == "/api/v1/health":
            await self.app(scope, receive, send)
            return
        client = scope.get("client")
        key = client[0] if client else "unknown"
        allowed, remaining = self.limiter.check(key)
        limit_headers = [
            (b"x-ratelimit-limit", str(self.limiter.limit).encode("ascii")),
            (b"x-ratelimit-remaining", str(remaining).encode("ascii")),
        ]
        if not allowed:
            body = json.dumps(
                {
                    "detail": (
                        "Rate limit exceeded. This limit is process-local and is not "
                        "a distributed control."
                    )
                }
            ).encode("utf-8")
            headers = [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
                (b"retry-after", b"60"),
                *limit_headers,
            ]
            await send({"type": "http.response.start", "status": 429, "headers": headers})
            await send({"type": "http.response.body", "body": body})
            return

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(limit_headers)
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_wrapper)
