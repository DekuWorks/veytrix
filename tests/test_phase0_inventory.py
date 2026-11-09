"""Phase 0 inventory docs must match the code they describe."""

import importlib.util
import re
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
ROSTER = ROOT / "docs" / "phase-0" / "agent-roster.md"
ENVIRONMENT = ROOT / "docs" / "phase-0" / "environment.md"
VERSIONS = ROOT / "services" / "api" / "alembic" / "versions"

ROSTER_ROW = re.compile(
    r"^\| `(?P<code>[A-Z]+-01)` \| `(?P<id>[0-9a-f-]{36})` \| (?P<name>[^|]+?) \| "
    r"`(?P<desk>[a-z-]+)` \| (?P<fx>\d+), (?P<fy>\d+) \| (?P<bx>\d+), (?P<by>\d+) \|$",
    re.MULTILINE,
)


def _migration(filename: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(filename, VERSIONS / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _roster() -> dict[str, dict[str, str]]:
    text = ROSTER.read_text(encoding="utf-8")
    return {match["code"]: match.groupdict() for match in ROSTER_ROW.finditer(text)}


def _tiles(source: str, name: str) -> dict[str, tuple[int, int]]:
    block = re.search(rf"export const {name}[^=]*= \{{(.*?)\n\}};", source, re.DOTALL)
    assert block, name
    return {
        code: (int(x), int(y))
        for code, x, y in re.findall(r'"([A-Z]+-01)": \{ x: (\d+), y: (\d+) \}', block.group(1))
    }


def test_roster_matches_the_registry_migrations() -> None:
    roster = _roster()
    seeded = {
        code: (agent_id, display_name, desk)
        for agent_id, code, display_name, desk in _migration(
            "20261108_0009_agent_registry.py"
        ).AGENT_ROWS
    }
    futures = _migration("20261109_0010_futures_desk.py")
    futures_source = (VERSIONS / "20261109_0010_futures_desk.py").read_text(encoding="utf-8")
    assert "'FUTURES-01', 'Futures desk', 'futures-research'" in futures_source
    seeded["FUTURES-01"] = (futures.FUTURES_ID, "Futures desk", "futures-research")

    assert len(seeded) == 10
    assert set(roster) == set(seeded)
    for code, (agent_id, display_name, desk) in seeded.items():
        row = roster[code]
        assert (row["id"], row["name"], row["desk"]) == (agent_id, display_name, desk), code


def test_roster_matches_the_web_codes_and_sanctum_tiles() -> None:
    roster = _roster()
    types = (ROOT / "apps" / "web" / "src" / "api" / "types.ts").read_text(encoding="utf-8")
    codes_block = re.search(r"export const AGENT_CODES = \[(.*?)\] as const;", types, re.DOTALL)
    assert codes_block
    web_codes = set(re.findall(r'"([A-Z]+-01)"', codes_block.group(1)))
    floor = (ROOT / "apps" / "web" / "src" / "sanctum" / "floor.ts").read_text(encoding="utf-8")
    desks = _tiles(floor, "DESK_TILES")
    seats = _tiles(floor, "BOARDROOM_SEATS")

    assert web_codes == set(roster) == set(desks) == set(seats)
    for code, row in roster.items():
        assert desks[code] == (int(row["fx"]), int(row["fy"])), code
        assert seats[code] == (int(row["bx"]), int(row["by"])), code


def test_roster_does_not_invent_unmapped_agents() -> None:
    roster = _roster()

    assert "LIEN-01" not in roster
    for persona in ("Astra", "Dayvid", "Atlas"):
        assert all(persona not in row["name"] for row in roster.values())


def _env_names_read_by_code() -> set[str]:
    names: set[str] = set()
    for path in (ROOT / "services").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        names.update(re.findall(r'AliasChoices\(\s*"([A-Z][A-Z0-9_]+)"', text))
        names.update(re.findall(r'os\.environ(?:\.get)?\(\s*"([A-Z][A-Z0-9_]+)"', text))
        names.update(re.findall(r'os\.environ\[\s*"([A-Z][A-Z0-9_]+)"', text))
        names.update(re.findall(r'os\.getenv\(\s*"([A-Z][A-Z0-9_]+)"', text))
    for path in (ROOT / "apps" / "web" / "src").rglob("*.ts*"):
        names.update(
            re.findall(r"import\.meta\.env\.([A-Z][A-Z0-9_]+)", path.read_text(encoding="utf-8"))
        )
    for path in (ROOT / "services").rglob("*.yaml"):
        names.update(
            re.findall(r"rpc_env_var:\s*([A-Z][A-Z0-9_]+)", path.read_text(encoding="utf-8"))
        )
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    names.update(re.findall(r"\$\{([A-Z][A-Z0-9_]+)", compose))
    return names


def test_environment_inventory_lists_every_variable_the_code_reads() -> None:
    documented = set(
        re.findall(r"^\| `([A-Z][A-Z0-9_]+)` \|", ENVIRONMENT.read_text(encoding="utf-8"), re.M)
    )
    read = _env_names_read_by_code()

    assert {"VEYTRIX_ENABLE_LIVE_BROKER", "ALPACA_LIVE_SECRET_KEY", "VITE_API_BASE_URL"} <= read
    assert read - documented == set()


def test_no_browser_variable_looks_like_a_secret() -> None:
    browser = {name for name in _env_names_read_by_code() if name.startswith("VITE_")}

    assert browser
    for name in browser:
        for marker in ("SECRET", "SERVICE_ROLE", "PRIVATE", "PASSWORD"):
            assert marker not in name, name
