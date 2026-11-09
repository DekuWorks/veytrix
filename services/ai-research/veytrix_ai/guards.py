"""Pure guards for the simulated paper-swap CLI."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import ROUND_DOWN, ROUND_UP, Decimal, InvalidOperation
from pathlib import Path

from veytrix_ai.config import MAX_SLIPPAGE_BPS_CEILING, SwapbotConfig

BPS = 10_000
_KEY_ENV = ("PRIVATE_KEY", "MNEMONIC", "SEED_PHRASE")


class GuardError(RuntimeError):
    pass


class KillSwitch:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    @property
    def engaged(self) -> bool:
        return self.path.exists()

    def check(self) -> None:
        if self.engaged:
            raise GuardError(f"kill switch is engaged ({self.path.name}); run `resume` to clear")

    def engage(self, reason: str = "") -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).isoformat(timespec="seconds")
        self.path.write_text(f"{stamp} {reason}".strip() + "\n", encoding="utf-8")

    def release(self) -> bool:
        if self.path.exists():
            self.path.unlink()
            return True
        return False


def refuse_key_material(env: Mapping[str, str]) -> None:
    """Refuse to run when the environment is holding key material."""

    for name, value in env.items():
        if not value:
            continue
        upper = name.upper()
        if any(upper.endswith(suffix) for suffix in _KEY_ENV):
            raise GuardError("private key material is not accepted")


def parse_amount(raw: str | Decimal) -> Decimal:
    if isinstance(raw, float | bool):
        raise GuardError("amount must be a decimal string, not a float")
    try:
        value = Decimal(raw) if isinstance(raw, str) else raw
    except InvalidOperation:
        raise GuardError("amount is not a decimal") from None
    if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
        raise GuardError("amount must be a positive decimal")
    return value


def to_base_units(amount: Decimal, decimals: int) -> int:
    scaled = amount.scaleb(decimals)
    if scaled != scaled.to_integral_value():
        raise GuardError(f"amount has more than {decimals} decimal places")
    base = int(scaled)
    if base <= 0:
        raise GuardError("amount rounds to zero base units")
    return base


def from_base_units(base: int, decimals: int) -> Decimal:
    if base <= 0:
        raise GuardError("quote returned zero output")
    return Decimal(base).scaleb(-decimals)


def effective_slippage_bps(config: SwapbotConfig, requested: int | None) -> int:
    """Callers may tighten slippage. They cannot loosen it past the config."""

    if requested is None:
        return config.max_slippage_bps
    if isinstance(requested, bool) or not isinstance(requested, int) or requested < 1:
        raise GuardError("slippage_bps must be a positive integer")
    if requested > config.max_slippage_bps or requested > MAX_SLIPPAGE_BPS_CEILING:
        raise GuardError(f"slippage_bps {requested} exceeds max {config.max_slippage_bps}")
    return requested


def apply_slippage(quoted: Decimal, slippage_bps: int, decimals: int) -> Decimal:
    """Reduce a quoted output by slippage using Decimal, never float."""

    if isinstance(quoted, float) or not isinstance(quoted, Decimal):
        raise GuardError("quoted amount must be a Decimal")
    if not quoted.is_finite() or quoted <= 0:
        raise GuardError("quote returned zero output")
    if not 0 < slippage_bps < BPS:
        raise GuardError("slippage out of range")
    quantum = Decimal(1).scaleb(-decimals)
    net = (quoted * (Decimal(BPS) - Decimal(slippage_bps)) / Decimal(BPS)).quantize(
        quantum, rounding=ROUND_DOWN
    )
    if net <= 0:
        raise GuardError("output rounds to zero after slippage")
    return net


def native_fee(gas_units: int, gas_price_wei: int, decimals: int) -> Decimal:
    if isinstance(gas_units, bool) or isinstance(gas_price_wei, bool):
        raise GuardError("fee estimate was not positive")
    if gas_units <= 0 or gas_price_wei <= 0:
        raise GuardError("fee estimate was not positive")
    quantum = Decimal(1).scaleb(-decimals)
    fee = (Decimal(gas_units) * Decimal(gas_price_wei) / (Decimal(10) ** decimals)).quantize(
        quantum, rounding=ROUND_UP
    )
    if fee <= 0:
        raise GuardError("fee estimate rounds to zero")
    return fee


def decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"
