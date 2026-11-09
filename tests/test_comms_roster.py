"""The code-to-name map is read from the code. If any layer drifts, this fails."""

from __future__ import annotations

import re
from pathlib import Path

from veytrix_api.comms import roster
from veytrix_api.model_router import PERSONAS

ROOT = Path(__file__).resolve().parents[1]
VERSIONS = ROOT / "services/api/alembic/versions"
EXPECTED = {
    "SUPERVISOR-01": ("Roads", "AI Commander"),
    "DAY-01": ("Dayvid", "Day desk"),
    "STOCK-01": ("Vex", "Stock desk"),
    "CRYPTO-01": ("Nyx", "Crypto desk"),
    "DEFI-01": ("Cipher", "DeFi desk"),
    "ETF-01": ("Lyra", "ETF desk"),
    "RESEARCH-01": ("Astra", "Research desk"),
    "RISK-01": ("Aegis", "Risk desk"),
    "TREASURY-01": ("Midas", "Treasury desk"),
    "FUTURES-01": ("Futures", "Futures desk"),
}


def test_roster_matches_the_expected_map() -> None:
    assert {d.code: (d.name, d.role) for d in roster.DESKS} == EXPECTED


def test_registry_ids_and_desk_slugs_match_the_migrations() -> None:
    nine = (VERSIONS / "20261108_0009_agent_registry.py").read_text()
    ten = (VERSIONS / "20261109_0010_futures_desk.py").read_text()
    rows = re.findall(r'\("(a1[0-9a-f-]{34})", "([A-Z]+-01)", "[^"]+", "([a-z-]+)"\)', nine)
    assert len(rows) == 9
    futures_id = re.search(r'FUTURES_ID = "([0-9a-f-]+)"', ten).group(1)
    futures_desk = re.search(r"'FUTURES-01', 'Futures desk', '([a-z-]+)'", ten).group(1)
    rows.append((futures_id, "FUTURES-01", futures_desk))
    assert {code: (rid, slug) for rid, code, slug in rows} == {
        d.code: (d.registry_id, d.desk) for d in roster.DESKS
    }


def test_model_router_personas_agree_except_for_futures() -> None:
    assert PERSONAS == {c: n for c, (n, _r) in EXPECTED.items() if c != "FUTURES-01"}


def test_sanctum_page_roster_and_sky_floor_crew_agree() -> None:
    page = (ROOT / "apps/web/src/pages/SanctumPage.tsx").read_text()
    block = page[page.index("const ROSTER") : page.index("const PERSONAS")]
    web = dict(
        (code, (name, role))
        for code, name, role in re.findall(
            r'"([A-Z]+-01)": \{ name: "([^"]+)", role: "([^"]+)" \}', block
        )
    )
    assert web == EXPECTED
    sky = (ROOT / "apps/web/src/sanctum/ui/SkyFloor.tsx").read_text()
    crew = {
        code: (name, role)
        for code, name, role in re.findall(
            r'code: "([A-Z]+-01)", name: "([^"]+)", role: "([^"]+)"', sky
        )
    }
    assert crew == EXPECTED
