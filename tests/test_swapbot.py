"""Simulated paper swaps. No network, no signing."""

from __future__ import annotations

import ast
import copy
import io
import json
import uuid
from contextlib import redirect_stdout
from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from veytrix_ai import swapbot
from veytrix_ai.config import (
    FORBIDDEN_KEYS,
    TOP_KEYS,
    ConfigError,
    load_config,
    parse_config,
)
from veytrix_ai.engine import SwapEngine
from veytrix_ai.guards import GuardError, KillSwitch, apply_slippage
from veytrix_ai.quote import (
    COINBASE_SOL_USD_SPOT,
    QUOTE_SOURCE_POOL,
    QUOTE_SOURCE_REFERENCE,
    SOLANA_DEVNET_GENESIS,
    SOLANA_MAINNET_GENESIS,
    HttpTransport,
    MarketReader,
)
from veytrix_api.db import get_db
from veytrix_api.main import create_app
from veytrix_api.models import (
    Base,
    BlockchainNetworkRow,
    PaperSwapFillRow,
    PaperSwapOrderRow,
    SimulatedWalletBalanceRow,
)

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "services" / "ai-research" / "veytrix_ai"
SEPOLIA_QUOTER = "0xEd1f6473345F45b75F8179591dd5bA1888cf2FB3"
ENV = {
    "ETHEREUM_SEPOLIA_RPC_URL": "http://127.0.0.1:8545",
    "BASE_SEPOLIA_RPC_URL": "http://127.0.0.1:8546",
    "SOLANA_DEVNET_RPC_URL": "http://127.0.0.1:8899",
}
# veytrix-local-postgres. Port 5432 is a different container and is not used here.
LOCAL_SWAP_DATABASE_URL = "postgresql+psycopg://veytrix:local-dev-only@127.0.0.1:5433/veytrix"


class FakeMarket:
    def __init__(
        self,
        *,
        amount_out: int = 100_000_000,
        gas: int = 100_000,
        gas_price: int = 1_000_000_000,
        chain_id: int | None = None,
        genesis: str = SOLANA_DEVNET_GENESIS,
        spot: str = "150.00",
    ) -> None:
        self.calls: list[tuple[str, str, object]] = []
        self.amount_out = amount_out
        self.gas = gas
        self.gas_price = gas_price
        self.chain_id = chain_id
        self.genesis = genesis
        self.spot = spot

    def rpc(self, url: str, method: str, params: list[object]) -> object:
        self.calls.append((url, method, params))
        if method == "eth_chainId":
            if self.chain_id is not None:
                return hex(self.chain_id)
            if url.endswith("8546"):
                return hex(84532)
            return hex(11155111)
        if method == "eth_gasPrice":
            return hex(self.gas_price)
        if method == "eth_call":
            body = self.amount_out.to_bytes(32, "big") + bytes(64) + self.gas.to_bytes(32, "big")
            return "0x" + body.hex()
        if method == "getGenesisHash":
            return self.genesis
        raise AssertionError(method)

    def get_json(self, url: str) -> dict[str, object]:
        self.calls.append((url, "GET", None))
        assert url == COINBASE_SOL_USD_SPOT
        return {"data": {"amount": self.spot, "base": "SOL", "currency": "USD"}}


def memory_session(*, enforce_foreign_keys: bool = False) -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    if enforce_foreign_keys:

        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    Base.metadata.create_all(
        engine,
        tables=[
            BlockchainNetworkRow.__table__,
            SimulatedWalletBalanceRow.__table__,
            PaperSwapOrderRow.__table__,
            PaperSwapFillRow.__table__,
        ],
    )
    return Session(engine)


def _swap_engine(session: Session, state_dir: Path) -> SwapEngine:
    config = load_config()
    return SwapEngine(
        config,
        MarketReader(config, ENV, FakeMarket()),
        KillSwitch(state_dir / "swapbot.KILL"),
        session,
    )


def _assert_swap_rows(session: Session, receipt: dict[str, object]) -> None:
    assert receipt["simulated"] is True
    assert receipt["recorded"] is True
    assert receipt["status"] == "simulated"
    order = session.get(PaperSwapOrderRow, uuid.UUID(str(receipt["order_id"])))
    assert order is not None
    fill = session.scalar(select(PaperSwapFillRow).where(PaperSwapFillRow.order_id == order.id))
    assert fill is not None
    assert order.simulated is True and order.status == "simulated"
    assert fill.simulated is True and fill.order_id == order.id
    assert order.amount_in == fill.amount_in == Decimal("0.01")
    assert order.amount_out == fill.amount_out == Decimal("99.5")
    assert order.quoted_out == Decimal("100")
    assert order.quoted_price == fill.quoted_price == Decimal("10000")
    assert order.fee_estimate == fill.fee_estimate == Decimal("0.0001")
    assert order.slippage_applied == fill.slippage_applied == Decimal("0.5")
    network = session.get(BlockchainNetworkRow, order.network_id)
    assert network is not None and network.simulated is True
    balances = {
        row.symbol: row.amount
        for row in session.scalars(
            select(SimulatedWalletBalanceRow).where(
                SimulatedWalletBalanceRow.network_id == network.id
            )
        )
    }
    assert balances["ETH"] == Decimal("0.9899")
    assert balances["USDC"] == Decimal("1099.5")
    stored = {symbol: Decimal(str(amount)) for symbol, amount in fill.balances_after.items()}
    assert stored["ETH"] == balances["ETH"]
    assert stored["USDC"] == balances["USDC"]
    reported = receipt["balances"]
    assert isinstance(reported, dict)
    assert Decimal(str(reported["ETH"])) == balances["ETH"]
    assert Decimal(str(reported["USDC"])) == balances["USDC"]


def _postgres_reachable(url: str) -> bool:
    if "127.0.0.1:5433" not in url and "localhost:5433" not in url:
        return False
    raw = url.replace("postgresql+psycopg://", "postgresql://", 1)
    try:
        import psycopg

        with psycopg.connect(raw, connect_timeout=2) as connection:
            connection.execute("SELECT 1")
    except Exception:
        return False
    return True


def _ledger_counts(url: str) -> tuple[int, int, int, int]:
    engine = create_engine(url)
    try:
        with Session(engine) as session:
            networks = int(
                session.scalar(select(func.count()).select_from(BlockchainNetworkRow)) or 0
            )
            balances = int(
                session.scalar(select(func.count()).select_from(SimulatedWalletBalanceRow)) or 0
            )
            orders = int(session.scalar(select(func.count()).select_from(PaperSwapOrderRow)) or 0)
            fills = int(session.scalar(select(func.count()).select_from(PaperSwapFillRow)) or 0)
    finally:
        engine.dispose()
    return networks, balances, orders, fills


def run(
    tmp_path: Path,
    args: list[str],
    session: Session | None = None,
    fake: FakeMarket | None = None,
    env: dict[str, str] | None = None,
) -> tuple[int, dict[str, object]]:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = swapbot.main(
            ["--state-dir", str(tmp_path), *args],
            environ=ENV if env is None else env,
            session=session,
            transport=fake if fake is not None else FakeMarket(),
        )
    text = buffer.getvalue().strip()
    payload = json.loads(text) if text else {}
    return code, payload


def test_checked_in_config_is_testnet_only_and_has_no_key_field() -> None:
    config = load_config()

    assert set(config.chains) == {"solana", "ethereum", "base"}
    assert config.chains["ethereum"].chain_id == "11155111"
    assert config.chains["base"].chain_id == "84532"
    assert config.chains["solana"].chain_id == "devnet"
    assert config.chains["ethereum"].starting_balances["ETH"] == Decimal("1")
    assert config.chains["base"].starting_balances["USDC"] == Decimal("1000")
    assert config.chains["solana"].starting_balances["SOL"] == Decimal("100")
    assert config.max_slippage_bps == 50
    assert "private_key" not in TOP_KEYS
    assert "private_key" in FORBIDDEN_KEYS
    assert config.chains["ethereum"].quoter == SEPOLIA_QUOTER


def test_mainnet_and_unknown_chains_are_refused() -> None:
    raw = yaml.safe_load((ROOT / "services" / "ai-research" / "swapbot.yaml").read_text())
    for name, bad in (("ethereum", 1), ("base", 8453), ("solana", "mainnet-beta")):
        edited = copy.deepcopy(raw)
        edited["chains"][name]["chain_id"] = bad
        with pytest.raises(ConfigError, match="not an allowed testnet"):
            parse_config(edited)
    unknown = copy.deepcopy(raw)
    unknown["chains"]["polygon"] = unknown["chains"]["ethereum"]
    with pytest.raises(ConfigError, match="no other chain"):
        parse_config(unknown)
    unknown["private_key"] = "not-used"
    with pytest.raises(ConfigError, match="key material"):
        parse_config(unknown)


def test_slippage_uses_decimal_not_float() -> None:
    assert apply_slippage(Decimal("100"), 50, 6) == Decimal("99.5")
    assert apply_slippage(Decimal("0.1"), 50, 18) == Decimal("0.0995")
    assert isinstance(apply_slippage(Decimal("2"), 50, 18), Decimal)
    with pytest.raises(GuardError):
        apply_slippage(0.1, 50, 18)  # type: ignore[arg-type]


def test_swap_receipt_is_simulated_and_applies_slippage_and_fee(tmp_path: Path) -> None:
    session = memory_session()
    fake = FakeMarket()
    code, payload = run(
        tmp_path,
        ["swap", "--chain", "ethereum", "ETH", "USDC", "0.01"],
        session,
        fake,
    )

    assert code == 0
    assert payload["simulated"] is True
    assert payload["signing"] is False
    assert payload["broadcast"] is False
    assert payload["status"] == "simulated"
    assert payload["quote_source"] == QUOTE_SOURCE_POOL
    assert payload["price_kind"] == "pool"
    assert Decimal(str(payload["amount_out"])) == Decimal("99.5")
    assert Decimal(str(payload["slippage_applied"])) == Decimal("0.5")
    assert Decimal(str(payload["fee_estimate"])) == Decimal("0.0001")
    assert payload["balances"] == {"ETH": "0.9899", "USDC": "1099.5"}
    call = next(item for item in fake.calls if item[1] == "eth_call")
    assert call[2][0]["to"] == SEPOLIA_QUOTER  # type: ignore[index]
    assert "eth_sendRawTransaction" not in {item[1] for item in fake.calls}
    order = session.scalar(select(PaperSwapOrderRow))
    fill = session.scalar(select(PaperSwapFillRow))
    assert order is not None and order.simulated is True and order.status == "simulated"
    assert fill is not None and fill.simulated is True
    assert "private_key" not in fill.balances_after


def test_swap_ledger_respects_foreign_keys(tmp_path: Path) -> None:
    session = memory_session(enforce_foreign_keys=True)
    assert session.connection().exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
    receipt = _swap_engine(session, tmp_path).swap("ethereum", "ETH", "USDC", "0.01")
    _assert_swap_rows(session, receipt)


def test_swap_ledger_commits_on_local_postgres(tmp_path: Path) -> None:
    if not _postgres_reachable(LOCAL_SWAP_DATABASE_URL):
        pytest.skip("PostgreSQL is not running on 127.0.0.1:5433.")
    before = _ledger_counts(LOCAL_SWAP_DATABASE_URL)
    engine = create_engine(LOCAL_SWAP_DATABASE_URL)
    connection = engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        receipt = _swap_engine(session, tmp_path).swap("ethereum", "ETH", "USDC", "0.01")
        _assert_swap_rows(session, receipt)
    finally:
        session.close()
        if connection.in_transaction():
            outer.rollback()
        connection.close()
        engine.dispose()
    assert _ledger_counts(LOCAL_SWAP_DATABASE_URL) == before


def test_insufficient_balance_is_refused_and_not_recorded(tmp_path: Path) -> None:
    session = memory_session()
    code, payload = run(
        tmp_path,
        ["swap", "--chain", "ethereum", "ETH", "USDC", "1"],
        session,
        FakeMarket(),
    )

    assert code == 2
    assert "insufficient ETH balance" in str(payload["refused"])
    assert session.scalar(select(PaperSwapOrderRow)) is None


def test_kill_switch_blocks_before_any_market_data_call(tmp_path: Path) -> None:
    fake = FakeMarket()
    code, _payload = run(tmp_path, ["kill", "--reason", "stop"])
    assert code == 0
    blocked, payload = run(
        tmp_path,
        ["swap", "--chain", "ethereum", "ETH", "USDC", "0.01"],
        memory_session(),
        fake,
    )
    assert blocked == 2
    assert "kill switch" in str(payload["refused"])
    assert fake.calls == []


def test_private_key_is_refused_and_not_echoed(tmp_path: Path) -> None:
    secret = "0x" + "ab" * 32
    code, payload = run(
        tmp_path,
        ["swap", "--chain", "ethereum", "ETH", "USDC", "0.01"],
        memory_session(),
        FakeMarket(),
        {**ENV, "SWAPBOT_PRIVATE_KEY": secret},
    )
    rendered = json.dumps(payload)
    assert code == 2
    assert "not accepted" in str(payload["refused"])
    assert secret not in rendered
    assert "ab" * 32 not in rendered


def test_broadcast_flag_is_refused(tmp_path: Path) -> None:
    code, payload = run(
        tmp_path,
        ["swap", "--chain", "ethereum", "ETH", "USDC", "0.01", "--broadcast"],
    )
    assert code == 2
    assert "broadcast" in str(payload["refused"])


def test_no_module_imports_eth_account_or_web3() -> None:
    for path in PACKAGE.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or "", *[alias.name for alias in node.names]]
            else:
                continue
            for name in names:
                assert "eth_account" not in name
                assert name not in {"web3", "eth_account"}
        assert "sign_transaction" not in path.read_text(encoding="utf-8")


def test_transport_refuses_mainnet_send_and_jupiter() -> None:
    def boom(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise AssertionError("network")

    transport = HttpTransport(sender=boom, getter=boom)
    with pytest.raises(GuardError, match="refused"):
        transport.rpc("https://mainnet.base.org", "eth_chainId", [])
    with pytest.raises(GuardError, match="refused"):
        transport.rpc("https://api.mainnet.solana.com", "getGenesisHash", [])
    with pytest.raises(GuardError, match="refused"):
        transport.rpc("https://cloudflare-eth.com", "eth_call", [])
    with pytest.raises(GuardError, match="refused"):
        transport.rpc("http://127.0.0.1:8545", "eth_sendRawTransaction", ["0x"])
    with pytest.raises(GuardError, match="refused"):
        transport.get_json("https://quote-api.jup.ag/v6/quote")


def test_reported_mainnet_chain_id_is_refused(tmp_path: Path) -> None:
    fake = FakeMarket(chain_id=1)
    code, payload = run(
        tmp_path,
        ["quote", "--chain", "ethereum", "ETH", "USDC", "0.01"],
        fake=fake,
    )
    assert code == 2
    assert "mainnet" in str(payload["refused"])
    assert [item[1] for item in fake.calls] == ["eth_chainId"]


def test_unknown_cli_chain_is_refused_without_a_call(tmp_path: Path) -> None:
    fake = FakeMarket()
    code, payload = run(tmp_path, ["quote", "--chain", "polygon", "ETH", "USDC", "1"], fake=fake)
    assert code == 2
    assert "unknown chain" in str(payload["refused"])
    assert fake.calls == []


def test_solana_uses_a_labelled_reference_price(tmp_path: Path) -> None:
    fake = FakeMarket()
    code, payload = run(
        tmp_path,
        ["swap", "--chain", "solana", "SOL", "USDC", "1"],
        memory_session(),
        fake,
    )
    assert code == 0
    assert payload["simulated"] is True
    assert payload["price_kind"] == "reference"
    assert payload["quote_source"] == QUOTE_SOURCE_REFERENCE
    assert Decimal(str(payload["amount_out"])) == Decimal("149.25")
    assert payload["balances"]["SOL"] == "98.999995"
    assert payload["balances"]["USDC"] == "1149.25"
    assert any(item[1] == "GET" for item in fake.calls)


def test_solana_mainnet_genesis_is_refused_before_the_reference_price(tmp_path: Path) -> None:
    fake = FakeMarket(genesis=SOLANA_MAINNET_GENESIS)
    code, payload = run(
        tmp_path,
        ["quote", "--chain", "solana", "SOL", "USDC", "1"],
        fake=fake,
    )
    assert code == 2
    assert "mainnet" in str(payload["refused"])
    assert "GET" not in {item[1] for item in fake.calls}


def test_api_reads_the_ledger_and_cannot_submit(tmp_path: Path) -> None:
    session = memory_session()
    code, _payload = run(
        tmp_path,
        ["swap", "--chain", "ethereum", "ETH", "USDC", "0.01"],
        session,
        FakeMarket(),
    )
    assert code == 0
    app = create_app()

    def override():
        yield session

    app.dependency_overrides[get_db] = override
    with TestClient(app) as client:
        portfolio = client.get("/api/v1/paper-swaps/portfolio")
        orders = client.get("/api/v1/paper-swaps/orders")
        posted = client.post("/api/v1/paper-swaps/orders", json={})

    assert portfolio.status_code == 200
    body = portfolio.json()
    assert body["simulated"] is True
    assert body["execution_permitted"] is False
    assert body["order_submitted"] is False
    ethereum = next(item for item in body["networks"] if item["chain"] == "ethereum")
    assert ethereum["simulated"] is True
    assert {row["symbol"]: row["amount"] for row in ethereum["balances"]} == {
        "ETH": "0.9899",
        "USDC": "1099.5",
    }
    assert orders.status_code == 200
    listed = orders.json()
    assert listed["orders"][0]["simulated"] is True
    assert listed["orders"][0]["status"] == "simulated"
    assert listed["orders"][0]["quote_source"] == QUOTE_SOURCE_POOL
    assert listed["orders"][0]["execution_permitted"] is False
    assert Decimal(listed["orders"][0]["amount_out"]) == Decimal("99.5")
    assert posted.status_code == 405
    paths = app.openapi()["paths"]
    assert set(paths["/api/v1/paper-swaps/portfolio"]) == {"get"}
    assert set(paths["/api/v1/paper-swaps/orders"]) == {"get"}
    router = (ROOT / "services" / "api" / "veytrix_api" / "routers" / "paper_swaps.py").read_text()
    assert "veytrix_ai" not in router
    assert "eth_account" not in router
