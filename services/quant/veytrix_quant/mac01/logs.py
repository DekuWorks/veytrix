"""Structured JSON decision log for MAC-01. Known secret values are masked in every record."""

from __future__ import annotations

import logging
from typing import Any

from veytrix_api.logging_config import JsonFormatter

LOGGER_NAME = "veytrix.mac01"


class SecretMaskingFilter(logging.Filter):
    def __init__(self, secrets: tuple[str, ...]) -> None:
        super().__init__()
        self.secrets = tuple(value for value in secrets if value)

    def _mask(self, value: Any) -> Any:
        if isinstance(value, str):
            for secret in self.secrets:
                value = value.replace(secret, "****")
        return value

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self._mask(record.getMessage())
        record.args = None
        for key, value in list(record.__dict__.items()):
            if isinstance(value, str) and key not in ("msg", "name", "levelname"):
                record.__dict__[key] = self._mask(value)
        return True


def configure(level: str = "INFO", secrets: tuple[str, ...] = ()) -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level.upper())
    logger.propagate = False
    for handler in list(logger.handlers):
        if handler.name == "mac01-json":
            logger.removeHandler(handler)
    for existing in list(logger.filters):
        if isinstance(existing, SecretMaskingFilter):
            logger.removeFilter(existing)
    masking = SecretMaskingFilter(secrets)
    logger.addFilter(masking)
    handler = logging.StreamHandler()
    handler.name = "mac01-json"
    handler.setFormatter(JsonFormatter())
    handler.addFilter(masking)
    logger.addHandler(handler)
    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger(LOGGER_NAME)


def event(name: str, **fields: Any) -> None:
    get_logger().info(name, extra={"event": name, **fields})
