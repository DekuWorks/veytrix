"""The ten desks as the Sanctum shows them. Names come from the code, not from a guess.

`tests/test_comms_roster.py` compares this table with the registry migrations, the
model router personas, and the web `ROSTER` and `CREW` tables. If one drifts, the
test fails. A desk here has no worker, no credential, and no order right.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Desk:
    code: str
    name: str
    role: str
    desk: str
    registry_id: str
    summary: str
    keywords: tuple[str, ...]


SUPERVISOR = "SUPERVISOR-01"
RISK = "RISK-01"

DESKS: tuple[Desk, ...] = (
    Desk(
        SUPERVISOR,
        "Roads",
        "AI Commander",
        "supervision",
        "a1000001-0000-4000-8000-000000000001",
        "Moderates discussions, reads every desk's registry row and the kill switch.",
        ("supervisor", "desk", "agency", "kill switch", "moderate", "boardroom", "status"),
    ),
    Desk(
        "DAY-01",
        "Dayvid",
        "Day desk",
        "equities-session",
        "a1000002-0000-4000-8000-000000000002",
        "Equities session view. Reads the MAC-01 ledger. Does not run it.",
        ("day", "intraday", "session", "aapl", "open", "close"),
    ),
    Desk(
        "STOCK-01",
        "Vex",
        "Stock desk",
        "equities-swing",
        "a1000003-0000-4000-8000-000000000003",
        "Equities swing view. Reads the MAC-01 signals and orders. Does not run it.",
        ("stock", "equity", "equities", "swing", "aapl", "sma", "crossover", "mac-01", "mac01"),
    ),
    Desk(
        "CRYPTO-01",
        "Nyx",
        "Crypto desk",
        "crypto-display",
        "a1000004-0000-4000-8000-000000000004",
        "Crypto display. Reads stored instruments and bars. Does not trade.",
        ("crypto", "btc", "bitcoin", "eth", "ethereum", "sol", "solana", "bars", "ticker"),
    ),
    Desk(
        "DEFI-01",
        "Cipher",
        "DeFi desk",
        "simulated-swap",
        "a1000005-0000-4000-8000-000000000005",
        "Reads simulated paper swaps. It cannot sign or broadcast.",
        ("defi", "swap", "amm", "uniswap", "testnet", "sepolia", "devnet", "slippage"),
    ),
    Desk(
        "ETF-01",
        "Lyra",
        "ETF desk",
        "etf",
        "a1000006-0000-4000-8000-000000000006",
        "ETF view. Reads stored instruments. No ETF data source is connected.",
        ("etf", "index", "fund", "expense ratio", "spy", "qqq"),
    ),
    Desk(
        "RESEARCH-01",
        "Astra",
        "Research desk",
        "research",
        "a1000007-0000-4000-8000-000000000007",
        "Reads research notes and source events. Treats both as untrusted text.",
        ("research", "note", "notes", "source", "news", "event", "thesis", "learning"),
    ),
    Desk(
        RISK,
        "Aegis",
        "Risk desk",
        "risk",
        "a1000008-0000-4000-8000-000000000008",
        "Reads the paper risk policy, size journal, and kill switch.",
        ("risk", "size", "sizing", "policy", "drawdown", "stop", "exposure", "limit", "kill"),
    ),
    Desk(
        "TREASURY-01",
        "Midas",
        "Treasury desk",
        "treasury",
        "a1000009-0000-4000-8000-000000000009",
        "Reads paper fills for a local month projection. It cannot move funds.",
        ("treasury", "payout", "distribution", "month", "reconcile", "reconciliation", "funds"),
    ),
    Desk(
        "FUTURES-01",
        "Futures",
        "Futures desk",
        "futures-research",
        "a100000a-0000-4000-8000-00000000000a",
        "Futures research. Disabled. No Topstep account is connected.",
        ("futures", "mes", "mnq", "topstep", "contract", "margin"),
    ),
)

BY_CODE: dict[str, Desk] = {desk.code: desk for desk in DESKS}
CODES: tuple[str, ...] = tuple(desk.code for desk in DESKS)
_BY_NAME: dict[str, Desk] = {desk.name.lower(): desk for desk in DESKS}
_MENTION = re.compile(r"@([A-Za-z0-9_-]{2,32})")
ALL_MENTIONS = frozenset({"all", "everyone", "team", "agents"})


def desk_for(code: str) -> Desk:
    desk = BY_CODE.get(code)
    if desk is None:
        raise KeyError(code)
    return desk


def name_of(code: str) -> str:
    desk = BY_CODE.get(code)
    return desk.name if desk else code


def mentions(text: str) -> tuple[list[str], bool]:
    """Return mentioned desk codes in order, and whether @all was used."""

    found: list[str] = []
    everyone = False
    for raw in _MENTION.findall(text):
        key = raw.lower()
        if key in ALL_MENTIONS:
            everyone = True
            continue
        desk = _BY_NAME.get(key) or BY_CODE.get(raw.upper())
        if desk is not None and desk.code not in found:
            found.append(desk.code)
    return found, everyone


def relevant_desks(text: str, *, limit: int = 3, exclude: tuple[str, ...] = ()) -> list[str]:
    """Desks whose keywords appear in the text, best match first. Ties follow roster order."""

    lowered = text.lower()
    scored: list[tuple[int, int, str]] = []
    for index, desk in enumerate(DESKS):
        if desk.code in exclude:
            continue
        score = 0
        if desk.name.lower() in lowered:
            score += 3
        for word in desk.keywords:
            if re.search(rf"(?<![a-z0-9]){re.escape(word)}(?![a-z0-9])", lowered):
                score += 1
        if score:
            scored.append((-score, index, desk.code))
    scored.sort()
    return [code for _, _, code in scored[:limit]]
