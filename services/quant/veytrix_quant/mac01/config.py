"""MAC-01 configuration, credentials, and the static half of the live gate. Fails closed."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Literal

import yaml
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "mac-01.yaml"
LIVE_CONFIRM_PHRASE = "I_UNDERSTAND_REAL_MONEY"
NOTIONAL_CEILING = Decimal("100.00")
CENT = Decimal("0.01")
# Alpaca Trading API key IDs start with PK (paper) or AK (live).
PAPER_KEY_PREFIX = "PK"
LIVE_KEY_PREFIX = "AK"

Mode = Literal["paper", "live"]


class UnsafeConfiguration(RuntimeError):
    """MAC-01 must not run with this configuration."""


class LiveGateRefused(UnsafeConfiguration):
    """A live-money condition is not met. Nothing is submitted."""


class MissingCredentials(RuntimeError):
    """Alpaca Trading API credentials for the selected mode are absent. No broker call is made."""


class Mac01Config(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: Literal["AAPL"]
    strategy: Literal["sma_crossover"]
    strategy_version: Literal["mac-01.3"]
    fast_period: int = Field(ge=2, le=200)
    slow_period: int = Field(ge=3, le=400)
    history_trading_days: int = Field(ge=3, le=1000)
    timeframe: Literal["1d"]
    long_only: Literal[True]
    allow_short_selling: Literal[False]
    broker: Literal["alpaca_trading_api"]
    mode: Mode = "paper"
    live_enabled: bool = False
    expected_account_number: str = Field(default="", max_length=32, pattern=r"^[A-Za-z0-9]*$")
    submit_orders: bool
    max_notional_per_trade: Decimal = Field(ge=1, le=NOTIONAL_CEILING)
    max_position_notional: Decimal = Field(ge=1, le=NOTIONAL_CEILING)
    max_orders_per_day: int = Field(ge=1, le=2)
    daily_loss_cutoff_usd: Decimal = Field(gt=0, le=NOTIONAL_CEILING)
    kill_switch: bool
    data_feed: Literal["iex", "sip"] = "iex"

    @field_validator(
        "max_notional_per_trade",
        "max_position_notional",
        "daily_loss_cutoff_usd",
        mode="before",
    )
    @classmethod
    def money_is_not_a_float(cls, value: object) -> object:
        if isinstance(value, float | bool):
            raise ValueError('Use a quoted decimal such as "100.00", not a float.')
        return value

    @field_validator("max_notional_per_trade", "max_position_notional", "daily_loss_cutoff_usd")
    @classmethod
    def money_has_cents_at_most(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value != value.quantize(CENT):
            raise ValueError("Use at most two decimal places.")
        return value

    @field_validator(
        "long_only",
        "allow_short_selling",
        "live_enabled",
        "submit_orders",
        "kill_switch",
        mode="before",
    )
    @classmethod
    def flags_are_real_booleans(cls, value: object) -> object:
        if not isinstance(value, bool):
            raise ValueError("Use true or false.")
        return value

    @field_validator(
        "fast_period", "slow_period", "history_trading_days", "max_orders_per_day", mode="before"
    )
    @classmethod
    def counts_are_integers(cls, value: object) -> object:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("Use an integer.")
        return value

    @field_validator("expected_account_number", mode="before")
    @classmethod
    def account_number_is_text(cls, value: object) -> object:
        if value is None:
            return ""
        if not isinstance(value, str):
            raise ValueError("Quote the account number as a string.")
        return value.strip()

    def model_post_init(self, _context: object) -> None:
        if self.slow_period <= self.fast_period:
            raise UnsafeConfiguration("slow_period must be greater than fast_period.")
        if self.history_trading_days < self.slow_period + 1:
            raise UnsafeConfiguration("history_trading_days must cover slow_period + 1 closes.")
        if self.max_notional_per_trade > self.max_position_notional:
            raise UnsafeConfiguration("max_notional_per_trade exceeds max_position_notional.")


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> Mac01Config:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise UnsafeConfiguration(f"Could not read MAC-01 config at {path.name}.") from exc
    if not isinstance(raw, dict):
        raise UnsafeConfiguration("MAC-01 config must be a mapping.")
    try:
        return Mac01Config.model_validate(raw)
    except UnsafeConfiguration:
        raise
    except ValueError as exc:
        fields = sorted({str(error["loc"][0]) for error in getattr(exc, "errors", lambda: [])()})
        detail = ", ".join(fields) if fields else "unknown field"
        raise UnsafeConfiguration(f"MAC-01 config is unsafe or invalid: {detail}.") from exc


class TradingEnvironment(BaseSettings):
    """Alpaca Trading API keys and the live confirmation, from the environment or `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    paper_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("ALPACA_PAPER_API_KEY", "paper_api_key")
    )
    paper_secret_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("ALPACA_PAPER_SECRET_KEY", "paper_secret_key")
    )
    live_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("ALPACA_LIVE_API_KEY", "live_api_key")
    )
    live_secret_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("ALPACA_LIVE_SECRET_KEY", "live_secret_key")
    )
    live_confirm: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("MAC01_LIVE_CONFIRM", "live_confirm")
    )

    def secrets(self) -> tuple[str, ...]:
        values = []
        for item in (
            self.paper_api_key,
            self.paper_secret_key,
            self.live_api_key,
            self.live_secret_key,
        ):
            if item is not None and item.get_secret_value().strip():
                values.append(item.get_secret_value().strip())
        return tuple(values)


def _value(secret: SecretStr | None) -> str:
    return secret.get_secret_value().strip() if secret is not None else ""


def credentials_for(config: Mac01Config, env: TradingEnvironment) -> tuple[str, str]:
    """The key pair for the configured mode. A key from the other mode is refused."""

    if config.mode == "live":
        key, secret = _value(env.live_api_key), _value(env.live_secret_key)
        names = "ALPACA_LIVE_API_KEY and ALPACA_LIVE_SECRET_KEY"
        wrong_prefix = PAPER_KEY_PREFIX
    else:
        key, secret = _value(env.paper_api_key), _value(env.paper_secret_key)
        names = "ALPACA_PAPER_API_KEY and ALPACA_PAPER_SECRET_KEY"
        wrong_prefix = LIVE_KEY_PREFIX
    if not key or not secret:
        raise MissingCredentials(f"{names} are required for mode {config.mode}. No broker call.")
    if key.upper().startswith(wrong_prefix):
        raise UnsafeConfiguration(
            f"The {config.mode} key ID looks like a key for the other mode. Refusing."
        )
    return key, secret


def static_live_gate_failures(
    config: Mac01Config, env: TradingEnvironment, submit_flag: bool
) -> list[str]:
    """Live-money conditions that need no broker call. Empty means these all hold."""

    failures: list[str] = []
    if config.mode != "live":
        failures.append("config mode is not live")
    if not config.live_enabled:
        failures.append("config live_enabled is not true")
    if _value(env.live_confirm) != LIVE_CONFIRM_PHRASE:
        failures.append(f"MAC01_LIVE_CONFIRM is not {LIVE_CONFIRM_PHRASE}")
    if not submit_flag:
        failures.append("the --submit flag is absent")
    if not config.submit_orders:
        failures.append("config submit_orders is not true")
    if not config.expected_account_number:
        failures.append("config expected_account_number is empty")
    if config.kill_switch:
        failures.append("config kill_switch is engaged")
    return failures


def assert_static_live_gate(
    config: Mac01Config, env: TradingEnvironment, submit_flag: bool
) -> None:
    """Live mode with --submit must pass every static condition, or nothing runs."""

    if config.mode != "live" or not submit_flag:
        return
    failures = static_live_gate_failures(config, env, submit_flag)
    if failures:
        raise LiveGateRefused("Live submission refused: " + "; ".join(failures) + ".")


def mask(text: str, secrets: tuple[str, ...]) -> str:
    masked = text
    for value in secrets:
        if value:
            masked = masked.replace(value, "****")
    return masked
