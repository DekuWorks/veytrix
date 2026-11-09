"""Optional Supabase Realtime doorbell, sent only after a message is durably stored.

The payload carries ids, never message text. The browser then reads the message from this
API, so a Realtime subscriber cannot see a transcript, and a Realtime event cannot create
a message, an order, or a verified status. If the URL or the server-side key is not set,
nothing is sent and the UI says Realtime is not configured. This module invents no project.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlparse
from urllib.request import Request, urlopen

logger = logging.getLogger("veytrix")

TOPIC = "veytrix-comms"
EVENT = "message"
Transport = Callable[[str, dict[str, str], bytes], int]


def _post(url: str, headers: dict[str, str], body: bytes) -> int:
    request = Request(url, data=body, headers=headers, method="POST")  # noqa: S310
    with urlopen(request, timeout=3) as response:  # noqa: S310
        return int(response.status)


def url_allowed(url: str) -> bool:
    """https anywhere, or http only on loopback (a local Supabase stack)."""

    parsed = urlparse(url)
    if parsed.scheme == "https" and parsed.hostname:
        return True
    return parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "localhost")


@dataclass
class Notifier:
    url: str = ""
    key: str = ""
    transport: Transport = _post

    @property
    def configured(self) -> bool:
        return bool(self.url and self.key and url_allowed(self.url))

    def status(self) -> str:
        return "configured" if self.configured else "not_configured"

    def publish(self, payload: dict[str, object]) -> str:
        """Return `published`, `failed`, or `not_configured`. Never raises."""

        if not self.configured:
            return "not_configured"
        allowed = {"conversation_id", "seq", "message_id", "sender_id", "origin"}
        body = json.dumps(
            {
                "messages": [
                    {
                        "topic": TOPIC,
                        "event": EVENT,
                        "private": False,
                        "payload": {k: str(v) for k, v in payload.items() if k in allowed},
                    }
                ]
            }
        ).encode()
        headers = {
            "Content-Type": "application/json",
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
        }
        try:
            code = self.transport(
                f"{self.url.rstrip('/')}/realtime/v1/api/broadcast", headers, body
            )
        except Exception:
            logger.warning("realtime publish failed")
            return "failed"
        return "published" if 200 <= code < 300 else "failed"
