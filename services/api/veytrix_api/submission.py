"""Evidence that this API process cannot submit a MAC-01 order.

The eight live-gate conditions are reported as booleans. The confirmation
phrase and the account number are never copied into the result.
"""

from __future__ import annotations

import os
from typing import Literal

from veytrix_quant.mac01.config import (
    LIVE_CONFIRM_PHRASE,
    Mac01Config,
    UnsafeConfiguration,
    load_config,
)

ConditionName = Literal[
    "mode_live",
    "live_enabled",
    "submit_orders",
    "confirm_phrase",
    "submit_flag",
    "account_match",
    "account_active",
    "kill_switch_off",
]

CONDITION_NAMES: tuple[ConditionName, ...] = (
    "mode_live",
    "live_enabled",
    "submit_orders",
    "confirm_phrase",
    "submit_flag",
    "account_match",
    "account_active",
    "kill_switch_off",
)


def confirm_phrase_matches() -> bool:
    """True only when the environment holds the expected phrase. The value is not returned."""

    return os.environ.get("MAC01_LIVE_CONFIRM", "") == LIVE_CONFIRM_PHRASE


def load_submission_config() -> Mac01Config | None:
    try:
        return load_config()
    except UnsafeConfiguration:
        return None


def condition_results(
    config: Mac01Config | None, *, confirm_matches: bool
) -> list[tuple[ConditionName, bool]]:
    """Eight conditions. This API never holds --submit, an account read, or the ledger switch."""

    mode_live = config is not None and config.mode == "live"
    live_enabled = config is not None and config.live_enabled is True
    submit_orders = config is not None and config.submit_orders is True
    return [
        ("mode_live", mode_live),
        ("live_enabled", live_enabled),
        ("submit_orders", submit_orders),
        ("confirm_phrase", confirm_matches),
        ("submit_flag", False),
        ("account_match", False),
        ("account_active", False),
        ("kill_switch_off", False),
    ]
