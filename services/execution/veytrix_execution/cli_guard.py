"""Checklist for operator-typed Alpaca CLI commands.

The checklist does not look up a binary, does not start a process, and does
not read API keys. Paper is the CLI's own default. Live flags fail the check.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

_SHELL = set(";|&<>`$\\\n\r*?")
_READ = frozenset(
    {
        ("version",),
        ("doctor",),
        ("profile", "list"),
        ("account", "get"),
        ("position", "list"),
        ("order", "list"),
        ("clock",),
        ("calendar",),
        ("asset", "get"),
        ("watchlist", "list"),
        ("data", "bars"),
        ("data", "quotes"),
        ("data", "latest-quote"),
        ("data", "latest-trade"),
        ("data", "snapshot"),
    }
)
_VALUE_FLAGS = frozenset(
    {
        "--symbol",
        "--start",
        "--timeframe",
        "--status",
        "--side",
        "--qty",
        "--type",
        "--limit-price",
        "--client-order-id",
    }
)
_READ_FLAGS = frozenset(
    {
        "--symbol",
        "--start",
        "--timeframe",
        "--status",
        "--csv",
        "--quiet",
        "--help",
    }
)
_DRY_RUN_FLAGS = _READ_FLAGS | {
    "--side",
    "--qty",
    "--type",
    "--limit-price",
    "--client-order-id",
    "--dry-run",
}
_MUTATING = frozenset(
    {
        ("order", "cancel"),
        ("order", "cancel-all"),
        ("order", "replace"),
        ("position", "close"),
        ("position", "close-all"),
    }
)

PAPER_EXAMPLES: tuple[tuple[str, ...], ...] = (
    ("alpaca", "version"),
    ("alpaca", "doctor"),
    ("alpaca", "profile", "list"),
    ("alpaca", "account", "get"),
    ("alpaca", "order", "list"),
    ("alpaca", "clock"),
    (
        "alpaca",
        "order",
        "submit",
        "--symbol",
        "AAPL",
        "--side",
        "buy",
        "--qty",
        "1",
        "--type",
        "market",
        "--dry-run",
    ),
)


@dataclass(frozen=True)
class CliCheck:
    allowed: bool
    executed: Literal[False]
    message: str


def review_environment(environ: Mapping[str, str]) -> CliCheck:
    """Reject a true live-trade flag. Do not copy any other variable into the result."""

    value = environ.get("ALPACA_LIVE_TRADE", "")
    if value.strip().lower() == "true":
        return CliCheck(
            False,
            False,
            "ALPACA_LIVE_TRADE is true. No command was run.",
        )
    return CliCheck(True, False, "ALPACA_LIVE_TRADE is not true. No command was run.")


def review_command(argv: object) -> CliCheck:
    if not isinstance(argv, list) or not argv or not all(isinstance(part, str) for part in argv):
        return CliCheck(False, False, "Pass a list of strings. Nothing was executed.")
    if argv[0] != "alpaca":
        return CliCheck(False, False, "The checklist only recognises a bare alpaca command name.")
    if any(_unsafe(part) for part in argv):
        return CliCheck(False, False, "Shell syntax is not accepted. Nothing was executed.")
    if any(part == "--live" or part.upper().startswith("ALPACA_LIVE_TRADE") for part in argv):
        return CliCheck(False, False, "Live trading flags are refused. Nothing was executed.")

    positionals, flags, values_ok = _split(argv)
    if not values_ok:
        return CliCheck(False, False, "A flag is missing its value. Nothing was executed.")
    if any(flag == "--live" for flag in flags):
        return CliCheck(False, False, "Live trading flags are refused. Nothing was executed.")

    if positionals in _MUTATING or (positionals[:1] == ("api",) and len(positionals) > 1):
        return CliCheck(False, False, "Mutating and raw API commands are refused.")
    if positionals == ("order", "submit"):
        if "--dry-run" not in flags:
            return CliCheck(
                False,
                False,
                "order submit is refused without --dry-run. Nothing was executed.",
            )
        if any(flag not in _DRY_RUN_FLAGS for flag in flags):
            return CliCheck(
                False,
                False,
                "order submit uses a flag outside the paper dry-run list.",
            )
        return CliCheck(
            True,
            False,
            "Dry-run is on the paper checklist. This process did not run it.",
        )
    if positionals not in _READ:
        return CliCheck(False, False, "Command is outside the paper read-only checklist.")
    if any(flag not in _READ_FLAGS for flag in flags):
        return CliCheck(False, False, "Command uses a flag outside the paper read-only checklist.")
    return CliCheck(True, False, "Read-only paper checklist entry. This process did not run it.")


def _unsafe(part: str) -> bool:
    return any(character in part for character in _SHELL) or part.startswith(("/", ".", "~"))


def _split(argv: list[str]) -> tuple[tuple[str, ...], list[str], bool]:
    positionals: list[str] = []
    flags: list[str] = []
    expect_value = False
    for part in argv[1:]:
        if expect_value:
            if part.startswith("-"):
                return tuple(positionals), flags, False
            expect_value = False
            continue
        if part.startswith("-"):
            flags.append(part)
            if part in _VALUE_FLAGS:
                expect_value = True
            continue
        positionals.append(part)
    if expect_value:
        return tuple(positionals), flags, False
    return tuple(positionals), flags, True
