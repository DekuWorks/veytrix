"""Process settings. Invalid or unsafe posture refuses to boot."""

from __future__ import annotations

from functools import lru_cache
from urllib.parse import urlparse

from pydantic import AliasChoices, Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from veytrix_api.ratelimit import LOOPBACK_SUSTAINED_PER_MINUTE

DEFAULT_DATABASE_URL = "postgresql+psycopg://veytrix:local-dev-only@127.0.0.1:5432/veytrix"
LOCAL_ORIGINS = (
    "http://127.0.0.1:5173",
    "http://localhost:5173",
)
ALLOWED_DATABASE_HOSTS = frozenset({"127.0.0.1", "localhost", "postgres"})


class BootRefused(RuntimeError):
    """The process must exit rather than serve an unsafe configuration."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    veytrix_env: str = Field(
        default="local",
        validation_alias=AliasChoices("VEYTRIX_ENV", "veytrix_env"),
    )
    veytrix_enable_live_broker: bool = Field(
        default=False,
        validation_alias=AliasChoices("VEYTRIX_ENABLE_LIVE_BROKER", "veytrix_enable_live_broker"),
    )
    database_url: str = Field(
        default=DEFAULT_DATABASE_URL,
        validation_alias=AliasChoices("DATABASE_URL", "database_url"),
    )
    rate_limit_per_minute: int = Field(
        default=LOOPBACK_SUSTAINED_PER_MINUTE,
        ge=1,
        le=10_000,
        validation_alias=AliasChoices("VEYTRIX_RATE_LIMIT_PER_MINUTE", "rate_limit_per_minute"),
    )
    log_level: str = Field(
        default="INFO",
        validation_alias=AliasChoices("VEYTRIX_LOG_LEVEL", "log_level"),
    )


def assert_boot_allowed(settings: Settings) -> None:
    """Fail closed before the process accepts traffic.

    There is no auth-gateway flag in this build. A non-local environment
    cannot opt in. Live broker mode cannot opt in either. The database host
    must be loopback or the Compose service name. This API process never
    places an order; the MAC-01 bot enforces its own live gate.
    """

    if settings.veytrix_enable_live_broker:
        raise BootRefused(
            "Refusing to boot: VEYTRIX_ENABLE_LIVE_BROKER is set. "
            "Live broker connections are not permitted."
        )
    if settings.veytrix_env != "local":
        raise BootRefused(
            "Refusing to boot: VEYTRIX_ENV is not local and no auth gateway is configured."
        )
    host = urlparse(settings.database_url).hostname
    if host not in ALLOWED_DATABASE_HOSTS:
        raise BootRefused(
            "Refusing to boot: DATABASE_URL host is not local. "
            "Allowed hosts are 127.0.0.1, localhost, and postgres."
        )


@lru_cache
def get_settings() -> Settings:
    try:
        settings = Settings()
    except ValidationError as exc:
        raise BootRefused(
            "Refusing to boot: configuration is invalid. "
            "Live broker mode and non-local environments are not accepted."
        ) from exc
    assert_boot_allowed(settings)
    return settings
