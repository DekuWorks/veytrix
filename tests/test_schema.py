import os
from decimal import Decimal
from pathlib import Path

import pytest

from veytrix_api.models import Base

MIGRATION = Path("services/api/alembic/versions/20261107_0001_baseline.py")
PAPER_MIGRATION = Path("services/api/alembic/versions/20261108_0002_paper_positions.py")
NOTE_MIGRATION = Path("services/api/alembic/versions/20261108_0003_research_notes.py")
SOL_MIGRATION = Path("services/api/alembic/versions/20261108_0004_sol_paper_symbol.py")
EVENT_MIGRATION = Path("services/api/alembic/versions/20261108_0005_source_events.py")
JOURNAL_MIGRATION = Path("services/api/alembic/versions/20261108_0006_paper_size_journal.py")
MAC01_MIGRATION = Path("services/api/alembic/versions/20261108_0007_mac01_ledger.py")
ROOT = Path(__file__).resolve().parents[1]


def test_metadata_matches_the_baseline_tables() -> None:
    assert set(Base.metadata.tables) == {
        "instruments",
        "price_bars",
        "risk_policies",
        "audit_events",
        "paper_positions",
        "research_notes",
        "source_events",
        "paper_size_journal",
        "mac01_signals",
        "mac01_orders",
        "mac01_state",
        "blockchain_networks",
        "simulated_wallet_balances",
        "paper_swap_orders",
        "paper_swap_fills",
        "private.agents",
        "private.agent_permissions",
        "private.agent_runs",
    }
    instruments = Base.metadata.tables["instruments"]
    assert {
        "asset_type",
        "venue",
        "symbol",
        "currency",
        "contract_multiplier",
        "tick_size",
        "timezone",
        "calendar",
    } <= set(instruments.c.keys())
    bars = Base.metadata.tables["price_bars"]
    expected_bar_columns = {
        "bar_start",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "source_id",
        "ingested_at",
    }
    assert expected_bar_columns <= set(bars.c.keys())
    unique_names = {constraint.name for constraint in bars.constraints}
    assert "uq_price_bars_instrument_bar_start" in unique_names
    policy = Base.metadata.tables["risk_policies"]
    assert "ck_risk_policies_paper_only" in {constraint.name for constraint in policy.constraints}
    assert "ck_risk_policies_stops_not_enforced" in {
        constraint.name for constraint in policy.constraints
    }
    paper = Base.metadata.tables["paper_positions"]
    assert {
        "symbol",
        "entry",
        "stop",
        "shares",
        "notional",
        "planned_risk",
        "binding_constraint",
        "exchange_time",
        "recorded_at",
    } <= set(paper.c.keys())
    assert "order_id" not in paper.c.keys()
    assert "broker_id" not in paper.c.keys()
    assert "status" not in paper.c.keys()
    symbol_check = next(
        constraint
        for constraint in paper.constraints
        if constraint.name == "ck_paper_positions_symbol"
    )
    assert "SOL-USD" in str(symbol_check.sqltext)
    assert "DOGE-USD" not in str(symbol_check.sqltext)
    notes = Base.metadata.tables["research_notes"]
    assert {"title", "body", "created_at"} <= set(notes.c.keys())
    assert "symbol" not in notes.c.keys()
    assert "order_id" not in notes.c.keys()
    events = Base.metadata.tables["source_events"]
    assert {
        "title",
        "source",
        "event_time",
        "first_public_at",
        "recorded_at",
    } <= set(events.c.keys())
    assert "symbol" not in events.c.keys()
    assert "order_id" not in events.c.keys()
    assert "broker_id" not in events.c.keys()
    journal = Base.metadata.tables["paper_size_journal"]
    assert {
        "recorded_at",
        "symbol",
        "equity",
        "entry",
        "stop",
        "shares",
        "planned_risk",
        "binding_constraint",
        "execution_permitted",
        "order_submitted",
    } <= set(journal.c.keys())
    assert "order_id" not in journal.c.keys()
    assert "broker_id" not in journal.c.keys()
    assert "fill" not in journal.c.keys()
    assert "notional" not in journal.c.keys()


def test_migration_seeds_one_policy_and_no_prices() -> None:
    text = MIGRATION.read_text(encoding="utf-8")

    assert text.count("INSERT INTO risk_policies") == 1
    assert "INSERT INTO price_bars" not in text
    assert "INSERT INTO instruments" not in text
    assert "experimental-paper-default" in text
    assert "0.005" in text
    assert "enforced against a ledger" in text
    for table in ("instruments", "price_bars", "risk_policies", "audit_events"):
        assert table in text
    assert "paper_positions" not in text
    assert "research_notes" not in text
    assert "paper_size_journal" not in text


def test_paper_position_migration_stores_a_size_and_not_a_fill() -> None:
    text = PAPER_MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "0002_paper_positions"' in text
    assert 'down_revision: str | None = "0001_baseline"' in text
    assert "paper_positions" in text
    assert "INSERT INTO" not in text
    for column in (
        "symbol",
        "entry",
        "stop",
        "shares",
        "notional",
        "planned_risk",
        "binding_constraint",
        "exchange_time",
        "recorded_at",
    ):
        assert column in text
    assert "order_id" not in text
    assert "broker" not in text
    assert "research_notes" not in text


def test_research_note_migration_stores_text_and_not_a_trade() -> None:
    text = NOTE_MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "0003_research_notes"' in text
    assert 'down_revision: str | None = "0002_paper_positions"' in text
    assert "research_notes" in text
    assert "INSERT INTO" not in text
    for column in ("title", "body", "created_at"):
        assert column in text
    assert "symbol" not in text
    assert "order_id" not in text
    assert "broker" not in text


def test_sol_paper_symbol_migration_widens_the_allowlist() -> None:
    text = SOL_MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "0004_sol_paper_symbol"' in text
    assert 'down_revision: str | None = "0003_research_notes"' in text
    assert "SOL-USD" in text
    assert "INSERT INTO" not in text
    assert "order_id" not in text
    assert "broker" not in text


def test_source_event_migration_stores_a_typed_record_and_not_a_trade() -> None:
    text = EVENT_MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "0005_source_events"' in text
    assert 'down_revision: str | None = "0004_sol_paper_symbol"' in text
    assert "source_events" in text
    assert "INSERT INTO" not in text
    for column in ("title", "source", "event_time", "first_public_at", "recorded_at"):
        assert column in text
    assert 'sa.Column("symbol"' not in text
    assert "order_id" not in text
    assert "broker" not in text


def test_paper_size_journal_migration_stores_a_calculation_and_not_an_order() -> None:
    text = JOURNAL_MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "0006_paper_size_journal"' in text
    assert 'down_revision: str | None = "0005_source_events"' in text
    assert "paper_size_journal" in text
    assert "INSERT INTO" not in text
    for column in (
        "symbol",
        "equity",
        "entry",
        "stop",
        "shares",
        "planned_risk",
        "binding_constraint",
        "recorded_at",
        "execution_permitted",
        "order_submitted",
    ):
        assert column in text
    assert "order_id" not in text
    assert "broker_id" not in text
    assert "fill" not in text
    assert "execution_permitted = false" in text
    assert "order_submitted = false" in text


def test_mac01_migration_caps_buys_at_100_notional_and_seeds_no_prices() -> None:
    text = MAC01_MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "0007_mac01_ledger"' in text
    assert 'down_revision: str | None = "0006_paper_size_journal"' in text
    for table in ("mac01_signals", "mac01_orders", "mac01_state"):
        assert table in text
    assert "uq_mac01_signals_session" in text
    assert "uq_mac01_orders_client_order_id" in text
    assert "notional <= 100" in text
    assert "side = 'sell' AND qty IS NOT NULL AND notional IS NULL" in text
    assert "mode IN ('paper', 'live')" in text
    assert "symbol = 'AAPL'" in text
    assert text.count("INSERT INTO") == 1
    assert "INSERT INTO mac01_state" in text
    assert "INSERT INTO price_bars" not in text
    orders = Base.metadata.tables["mac01_orders"]
    names = {constraint.name for constraint in orders.constraints}
    assert {
        "uq_mac01_orders_client_order_id",
        "ck_mac01_orders_sizing",
        "ck_mac01_orders_mode",
    } <= names
    signals = Base.metadata.tables["mac01_signals"]
    assert "uq_mac01_signals_session" in {constraint.name for constraint in signals.constraints}


def test_paper_swap_migration_stores_simulated_fills_and_no_keys() -> None:
    text = Path("services/api/alembic/versions/20261108_0008_paper_swaps.py").read_text()

    assert 'revision: str = "0008_paper_swaps"' in text
    assert 'down_revision: str | None = "0007_mac01_ledger"' in text
    for table in (
        "blockchain_networks",
        "simulated_wallet_balances",
        "paper_swap_orders",
        "paper_swap_fills",
    ):
        assert table in text
    assert "INSERT INTO" not in text
    assert "private_key" not in text
    assert "simulated" in text
    assert "quote_source" in text
    assert "balances_after" in text
    orders = Base.metadata.tables["paper_swap_orders"]
    assert "private_key" not in orders.c.keys()
    names = {constraint.name for constraint in orders.constraints}
    assert "ck_paper_swap_orders_simulated" in names
    networks = Base.metadata.tables["blockchain_networks"]
    chain_check = next(
        constraint
        for constraint in networks.constraints
        if constraint.name == "ck_blockchain_networks_chain"
    )
    rendered = str(chain_check.sqltext)
    assert "11155111" in rendered
    assert "84532" in rendered
    assert "devnet" in rendered


def test_agent_registry_migration_is_private_and_cannot_trade() -> None:
    text = Path("services/api/alembic/versions/20261108_0009_agent_registry.py").read_text()

    assert 'revision: str = "0009_agent_registry"' in text
    assert 'down_revision: str | None = "0008_paper_swaps"' in text
    assert "CREATE SCHEMA IF NOT EXISTS private" in text
    assert "REVOKE ALL ON SCHEMA private FROM PUBLIC" in text
    assert "security_invoker = true" in text
    assert "FORCE ROW LEVEL SECURITY" in text
    assert "append-only row" in text
    assert "private_key" not in text
    assert "routing" not in text
    assert "service_role" not in text
    for code in (
        "SUPERVISOR-01",
        "DAY-01",
        "STOCK-01",
        "CRYPTO-01",
        "DEFI-01",
        "ETF-01",
        "RESEARCH-01",
        "RISK-01",
        "TREASURY-01",
    ):
        assert code in text
    for tool in (
        "submit_order",
        "sign_transaction",
        "broadcast_transaction",
        "bank_transfer",
        "set_live_mode",
        "release_kill_switch",
    ):
        assert tool in text
    agents = Base.metadata.tables["private.agents"]
    assert "private_key" not in agents.c.keys()
    assert "secret" not in agents.c.keys()
    assert "order_id" not in agents.c.keys()
    names = {constraint.name for constraint in agents.constraints}
    assert {
        "ck_agents_cannot_submit",
        "ck_agents_cannot_sign",
        "ck_agents_cannot_transfer",
        "ck_agents_no_credentials",
        "ck_agents_paper_only",
        "ck_agents_status",
    } <= names
    permissions = Base.metadata.tables["private.agent_permissions"]
    effect = next(
        constraint
        for constraint in permissions.constraints
        if constraint.name == "ck_agent_permissions_effect"
    )
    assert "deny" in str(effect.sqltext)
    runs = Base.metadata.tables["private.agent_runs"]
    assert "idempotency_key" in runs.c.keys()
    assert "broker_order_id" not in runs.c.keys()
    audit = Base.metadata.tables["audit_events"]
    assert "ck_audit_events_action" in {constraint.name for constraint in audit.constraints}
    assert "ix_audit_events_created_at" in {index.name for index in audit.indexes}


def _postgres_reachable(url: str) -> bool:
    if "127.0.0.1" not in url and "localhost" not in url:
        return False
    raw = url.replace("postgresql+psycopg://", "postgresql://", 1)
    try:
        import psycopg

        with psycopg.connect(raw, connect_timeout=2) as connection:
            connection.execute("SELECT 1")
    except Exception:
        return False
    return True


def _swap_database(url: str, database: str) -> str:
    base, _, query = url.partition("?")
    prefix, _current = base.rsplit("/", 1)
    swapped = f"{prefix}/{database}"
    return f"{swapped}?{query}" if query else swapped


def test_alembic_upgrade_on_postgres_16(monkeypatch: pytest.MonkeyPatch) -> None:
    source = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg://veytrix:local-dev-only@127.0.0.1:5432/veytrix",
    )
    if os.environ.get("CI") != "true" and ":5432/" in source:
        pytest.skip(
            "Refusing port 5432 outside CI. On this machine that port is daypilot-db. "
            "Set DATABASE_URL to 127.0.0.1:5433."
        )
    admin_url = _swap_database(source, "postgres")
    if os.environ.get("CI") == "true" and not _postgres_reachable(admin_url):
        pytest.fail("PostgreSQL was not reachable for the Alembic upgrade.")
    if not _postgres_reachable(admin_url):
        pytest.skip("PostgreSQL is not running on localhost. CI runs this upgrade.")

    import psycopg
    from alembic import command
    from alembic.config import Config

    from veytrix_api.settings import get_settings

    test_url = _swap_database(source, "veytrix_sprint0")
    raw_admin = admin_url.replace("postgresql+psycopg://", "postgresql://", 1)
    raw_test = test_url.replace("postgresql+psycopg://", "postgresql://", 1)
    try:
        with psycopg.connect(raw_admin, autocommit=True, connect_timeout=2) as connection:
            exists = connection.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                ("veytrix_sprint0",),
            ).fetchone()
            if exists is None:
                connection.execute("CREATE DATABASE veytrix_sprint0")
        with psycopg.connect(raw_test, autocommit=True, connect_timeout=2) as connection:
            connection.execute("DROP SCHEMA IF EXISTS private CASCADE")
            connection.execute("DROP SCHEMA public CASCADE")
            connection.execute("CREATE SCHEMA public")
    except Exception:
        if os.environ.get("CI") == "true":
            raise
        pytest.skip("Could not prepare the local sprint database.")

    monkeypatch.setenv("DATABASE_URL", test_url)
    monkeypatch.setenv("VEYTRIX_ENV", "local")
    monkeypatch.setenv("VEYTRIX_ENABLE_LIVE_BROKER", "0")
    get_settings.cache_clear()
    try:
        command.upgrade(Config(str(ROOT / "services/api/alembic.ini")), "head")
        with psycopg.connect(raw_test, connect_timeout=2) as connection:
            policy_count = connection.execute("SELECT count(*) FROM risk_policies").fetchone()[0]
            price_count = connection.execute("SELECT count(*) FROM price_bars").fetchone()[0]
            instrument_count = connection.execute("SELECT count(*) FROM instruments").fetchone()[0]
            paper_count = connection.execute("SELECT count(*) FROM paper_positions").fetchone()[0]
            note_count = connection.execute("SELECT count(*) FROM research_notes").fetchone()[0]
            event_count = connection.execute("SELECT count(*) FROM source_events").fetchone()[0]
            journal_count = connection.execute(
                "SELECT count(*) FROM paper_size_journal"
            ).fetchone()[0]
            mac01_counts = connection.execute(
                """
                SELECT (SELECT count(*) FROM mac01_signals),
                       (SELECT count(*) FROM mac01_orders),
                       (SELECT count(*) FROM mac01_state WHERE paused = false
                          AND kill_switch = false)
                """
            ).fetchone()
            symbol_check = connection.execute(
                """
                SELECT pg_get_constraintdef(oid)
                FROM pg_constraint
                WHERE conname = 'ck_paper_positions_symbol'
                """
            ).fetchone()
            row = connection.execute(
                """
                SELECT trading_mode, experimental, daily_stop_enforced, weekly_stop_enforced,
                       per_trade_risk_fraction, max_allocation_fraction
                FROM risk_policies
                """
            ).fetchone()
            agency = connection.execute(
                """
                SELECT count(*),
                       bool_and(can_submit_orders = false),
                       bool_and(can_sign = false),
                       bool_and(can_transfer_funds = false),
                       bool_and(paper_only),
                       bool_and(holds_credentials = false),
                       bool_and(status = 'disabled')
                FROM private.agents
                """
            ).fetchone()
            permission_count = connection.execute(
                """
                SELECT count(*) FROM private.agent_permissions
                WHERE effect = 'deny'
                """
            ).fetchone()[0]
            public_agents = connection.execute(
                """
                SELECT count(*) FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'agents'
                """
            ).fetchone()[0]
            rls = connection.execute(
                """
                SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
                FROM pg_class AS c
                JOIN pg_namespace AS n ON n.oid = c.relnamespace
                WHERE n.nspname = 'private' AND c.relkind = 'r'
                ORDER BY c.relname
                """
            ).fetchall()
            view_options = connection.execute(
                """
                SELECT c.reloptions
                FROM pg_class AS c
                JOIN pg_namespace AS n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND c.relname = 'agent_registry'
                """
            ).fetchone()
        _assert_registry_rejects_writes(raw_test)
    finally:
        get_settings.cache_clear()

    assert policy_count == 1
    assert price_count == 0
    assert instrument_count == 0
    assert paper_count == 0
    assert note_count == 0
    assert event_count == 0
    assert journal_count == 0
    assert tuple(mac01_counts) == (0, 0, 1)
    assert symbol_check is not None
    assert "SOL-USD" in symbol_check[0]
    assert "DOGE" not in symbol_check[0]
    assert row[0] == "paper"
    assert row[1] is True
    assert row[2] is False
    assert row[3] is False
    assert Decimal(str(row[4])) == Decimal("0.005")
    assert Decimal(str(row[5])) == Decimal("0.10")
    assert tuple(agency) == (9, True, True, True, True, True, True)
    assert permission_count == 63
    assert public_agents == 0
    assert {name: (row_security, force) for name, row_security, force in rls} == {
        "agent_permissions": (True, True),
        "agent_runs": (True, True),
        "agents": (True, True),
    }
    assert view_options is not None
    assert "security_invoker=true" in (view_options[0] or [])


def _assert_registry_rejects_writes(raw_test: str) -> None:
    import psycopg

    with psycopg.connect(raw_test, autocommit=True, connect_timeout=2) as connection:
        connection.execute(
            """
            INSERT INTO audit_events (id, correlation_id, action, payload)
            VALUES (gen_random_uuid(), 'registry-test', 'registry.read', '{"ok": true}'::jsonb)
            """
        )
        with pytest.raises(psycopg.Error, match="append-only row"):
            connection.execute("UPDATE audit_events SET action = 'mutated'")
        with pytest.raises(psycopg.Error, match="append-only row"):
            connection.execute("DELETE FROM audit_events")
        with pytest.raises(psycopg.Error, match="append-only row"):
            connection.execute("TRUNCATE audit_events")
        connection.execute("UPDATE private.agents SET status = 'paused' WHERE code = 'RISK-01'")
        paused = connection.execute(
            "SELECT status FROM private.agents WHERE code = 'RISK-01'"
        ).fetchone()
        assert paused is not None
        assert paused[0] == "paused"
        connection.execute("UPDATE private.agents SET status = 'disabled' WHERE code = 'RISK-01'")
        with pytest.raises(psycopg.Error, match="append-only columns on agents"):
            connection.execute("UPDATE private.agents SET can_submit_orders = true")
        with pytest.raises(psycopg.Error, match="append-only row"):
            connection.execute("DELETE FROM private.agents WHERE code = 'RISK-01'")
        with pytest.raises(psycopg.Error, match="check"):
            connection.execute(
                """
                INSERT INTO private.agent_permissions (id, agent_id, tool_name, effect)
                SELECT gen_random_uuid(), id, 'submit_order', 'allow'
                FROM private.agents
                WHERE code = 'SUPERVISOR-01'
                """
            )
        connection.execute(
            """
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'veytrix_rls_probe') THEN
                    EXECUTE 'REVOKE ALL ON public.agent_registry FROM veytrix_rls_probe';
                    EXECUTE 'REVOKE ALL ON private.agents FROM veytrix_rls_probe';
                    EXECUTE 'REVOKE USAGE ON SCHEMA public FROM veytrix_rls_probe';
                    EXECUTE 'REVOKE USAGE ON SCHEMA private FROM veytrix_rls_probe';
                    EXECUTE 'DROP ROLE veytrix_rls_probe';
                END IF;
            END $$
            """
        )
        connection.execute("CREATE ROLE veytrix_rls_probe NOLOGIN")
        try:
            connection.execute("GRANT veytrix_rls_probe TO CURRENT_USER")
            connection.execute("GRANT USAGE ON SCHEMA private TO veytrix_rls_probe")
            connection.execute("GRANT USAGE ON SCHEMA public TO veytrix_rls_probe")
            connection.execute("GRANT SELECT, INSERT ON private.agents TO veytrix_rls_probe")
            connection.execute("GRANT SELECT ON public.agent_registry TO veytrix_rls_probe")
            connection.execute("SET ROLE veytrix_rls_probe")
            seen = connection.execute("SELECT count(*) FROM private.agents").fetchone()
            view_seen = connection.execute("SELECT count(*) FROM public.agent_registry").fetchone()
            assert seen is not None and seen[0] == 0
            assert view_seen is not None and view_seen[0] == 0
            with pytest.raises(psycopg.Error, match="row-level security"):
                connection.execute(
                    """
                    INSERT INTO private.agents (
                        id, code, display_name, desk, status, paper_only,
                        can_submit_orders, can_sign, can_transfer_funds,
                        holds_credentials, notes
                    ) VALUES (
                        gen_random_uuid(), 'SUPERVISOR-01', 'Probe', 'supervision',
                        'disabled', true, false, false, false, false, 'probe'
                    )
                    """
                )
        finally:
            connection.execute("RESET ROLE")
            connection.execute("REVOKE ALL ON public.agent_registry FROM veytrix_rls_probe")
            connection.execute("REVOKE ALL ON private.agents FROM veytrix_rls_probe")
            connection.execute("REVOKE USAGE ON SCHEMA public FROM veytrix_rls_probe")
            connection.execute("REVOKE USAGE ON SCHEMA private FROM veytrix_rls_probe")
            connection.execute("DROP ROLE veytrix_rls_probe")
