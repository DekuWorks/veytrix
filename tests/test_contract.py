import json
import re
import tomllib
from pathlib import Path

from veytrix_api.main import create_app
from veytrix_market.sample import SAMPLE_DISCLAIMER
from veytrix_risk.sizing import STOPS_NOT_ENFORCED

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "packages" / "shared" / "openapi.json"
SPRINT_PATHS = {
    "/api/v1/health",
    "/api/v1/ready",
    "/api/v1/diagnostics",
    "/api/v1/market/instruments",
    "/api/v1/market/instruments/{symbol}/bars",
    "/api/v1/market/instruments/{symbol}/ticker",
    "/api/v1/risk/size",
    "/api/v1/portfolio/positions",
    "/api/v1/portfolio/positions/{position_id}",
    "/api/v1/research/notes",
    "/api/v1/research/notes/{note_id}",
    "/api/v1/research/source-events",
    "/api/v1/research/source-events/{event_id}",
    "/api/v1/audit/size-journal",
    "/api/v1/strategies/mac-01/status",
    "/api/v1/strategies/mac-01/signals",
    "/api/v1/strategies/mac-01/orders",
    "/api/v1/strategies/mac-01/performance",
    "/api/v1/strategies/mac-01/chart",
    "/api/v1/strategies/mac-01/pause",
    "/api/v1/strategies/mac-01/resume",
    "/api/v1/strategies/mac-01/kill-switch",
    "/api/v1/paper-swaps/portfolio",
    "/api/v1/paper-swaps/orders",
}


def test_openapi_snapshot_matches_the_app() -> None:
    assert SNAPSHOT.is_file(), "Run python scripts/export_openapi.py and commit the snapshot."
    committed = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    live = create_app().openapi()

    assert set(SPRINT_PATHS) <= set(live["paths"])
    assert live == committed


def test_ui_copy_matches_the_service_constants() -> None:
    source = (ROOT / "apps" / "web" / "src" / "content.ts").read_text(encoding="utf-8")

    assert SAMPLE_DISCLAIMER in source
    assert STOPS_NOT_ENFORCED in source


def test_compose_publishes_loopback_only_and_ci_asks_for_no_cloud_credentials() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8").lower()
    web_package = (ROOT / "apps" / "web" / "package.json").read_text(encoding="utf-8").lower()
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    optional = tomllib.loads(project)["project"]["optional-dependencies"]
    assert "chain" not in optional
    # alpaca-py is allowed once, pinned to a minor, for the MAC-01 bot's two adapters.
    dependencies = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "dependencies"
    ]
    alpaca_deps = [dep for dep in dependencies if "alpaca" in dep.lower()]
    assert alpaca_deps == ["alpaca-py>=0.45,<0.46"], alpaca_deps
    project = project.replace('"alpaca-py>=0.45,<0.46"', "").lower()

    assert "127.0.0.1:" in compose
    assert "0.0.0.0" not in compose
    assert "aws" not in workflow
    assert "vercel" not in workflow
    for banned in ("ccxt", "ib_insync", "alpaca", "vercel", "boto3", "web3", "ethers", "binance"):
        assert banned not in web_package
        assert banned not in project


MAC01_DIR = ROOT / "services" / "quant" / "veytrix_quant" / "mac01"
MAC01_ADAPTERS = {MAC01_DIR / "alpaca_trading.py", MAC01_DIR / "alpaca_data.py"}


def test_alpaca_is_reachable_only_from_the_mac01_adapters() -> None:
    """Only the two MAC-01 adapters may import alpaca-py. No module names an Alpaca host."""

    for path in (ROOT / "services").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        lower = text.lower()
        for banned in ("alpaca", "ccxt", "ib_insync", "boto3", "vercel", "binance", "requests"):
            pattern = rf"^\s*(?:import|from)\s+{banned}(?:\s|\.|,|$)"
            if path in MAC01_ADAPTERS and banned in ("alpaca", "requests"):
                continue
            assert not re.search(pattern, lower, re.MULTILINE), f"{path.name} imports {banned}"
        assert "import httpx" not in text, path.name
        assert "alpaca.markets" not in lower, path.name
        assert "url_override" not in lower, path.name


def test_api_process_cannot_reach_the_mac01_broker_path() -> None:
    """The API may read MAC-01 config and strategy maths, never the engine or adapters."""

    allowed = {"veytrix_quant.mac01", "veytrix_quant.mac01.config", "veytrix_quant.mac01.strategy"}
    for path in (ROOT / "services" / "api").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for module in re.findall(r"^\s*(?:from|import)\s+(veytrix_quant[\w.]*)", text, re.M):
            assert module in allowed, f"{path.name} imports {module}"


def test_quant_package_does_not_use_urlopen() -> None:
    for path in (ROOT / "services" / "quant").rglob("*.py"):
        assert "urlopen" not in path.read_text(encoding="utf-8").lower(), path.name


def test_market_package_does_not_call_a_broker() -> None:
    """Public Coinbase candles are allowed. Broker clients are not."""

    for path in (ROOT / "services" / "market-data").rglob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        for banned in ("binance", "broker", "ccxt", "alpaca"):
            assert banned not in text, path.name
        if path.name != "coinbase.py":
            assert "urlopen" not in text, path.name
