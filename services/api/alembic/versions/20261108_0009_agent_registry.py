"""Local agent registry in schema private, and an append-only audit log.

Existing public tables stay where they are. The API process already queries them.
This revision does not grant order, signing, or transfer rights.

Revision ID: 0009_agent_registry
Revises: 0008_paper_swaps
Create Date: 2026-11-08
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_agent_registry"
down_revision: str | None = "0008_paper_swaps"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AGENT_NOTES = (
    "Registry row only. This desk is not running. It cannot submit an order, "
    "sign a transaction, or move funds."
)
AGENT_ROWS = (
    ("a1000001-0000-4000-8000-000000000001", "SUPERVISOR-01", "Supervisor", "supervision"),
    ("a1000002-0000-4000-8000-000000000002", "DAY-01", "Day desk", "equities-session"),
    ("a1000003-0000-4000-8000-000000000003", "STOCK-01", "Stock desk", "equities-swing"),
    ("a1000004-0000-4000-8000-000000000004", "CRYPTO-01", "Crypto desk", "crypto-display"),
    ("a1000005-0000-4000-8000-000000000005", "DEFI-01", "DeFi desk", "simulated-swap"),
    ("a1000006-0000-4000-8000-000000000006", "ETF-01", "ETF desk", "etf"),
    ("a1000007-0000-4000-8000-000000000007", "RESEARCH-01", "Research desk", "research"),
    ("a1000008-0000-4000-8000-000000000008", "RISK-01", "Risk desk", "risk"),
    ("a1000009-0000-4000-8000-000000000009", "TREASURY-01", "Treasury desk", "treasury"),
)


def upgrade() -> None:
    op.execute(sa.text("CREATE SCHEMA IF NOT EXISTS private"))
    op.execute(sa.text("REVOKE ALL ON SCHEMA private FROM PUBLIC"))
    op.create_table(
        "agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=64), nullable=False),
        sa.Column("desk", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("paper_only", sa.Boolean(), nullable=False),
        sa.Column("can_submit_orders", sa.Boolean(), nullable=False),
        sa.Column("can_sign", sa.Boolean(), nullable=False),
        sa.Column("can_transfer_funds", sa.Boolean(), nullable=False),
        sa.Column("holds_credentials", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.String(length=500), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("code", name="uq_agents_code"),
        sa.CheckConstraint(
            "code IN ("
            "'SUPERVISOR-01', 'DAY-01', 'STOCK-01', 'CRYPTO-01', 'DEFI-01', "
            "'ETF-01', 'RESEARCH-01', 'RISK-01', 'TREASURY-01'"
            ")",
            name="ck_agents_code",
        ),
        sa.CheckConstraint("status IN ('disabled', 'paused')", name="ck_agents_status"),
        sa.CheckConstraint("paper_only", name="ck_agents_paper_only"),
        sa.CheckConstraint("can_submit_orders = false", name="ck_agents_cannot_submit"),
        sa.CheckConstraint("can_sign = false", name="ck_agents_cannot_sign"),
        sa.CheckConstraint("can_transfer_funds = false", name="ck_agents_cannot_transfer"),
        sa.CheckConstraint("holds_credentials = false", name="ck_agents_no_credentials"),
        sa.CheckConstraint(
            "char_length(display_name) BETWEEN 1 AND 64",
            name="ck_agents_display_name",
        ),
        sa.CheckConstraint("char_length(notes) BETWEEN 1 AND 500", name="ck_agents_notes"),
        schema="private",
    )
    op.create_table(
        "agent_permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tool_name", sa.String(length=64), nullable=False),
        sa.Column("effect", sa.String(length=8), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["private.agents.id"],
            name="fk_agent_permissions_agent_id",
        ),
        sa.UniqueConstraint("agent_id", "tool_name", name="uq_agent_permissions_agent_tool"),
        sa.CheckConstraint("effect = 'deny'", name="ck_agent_permissions_effect"),
        sa.CheckConstraint(
            "tool_name IN ("
            "'submit_order', 'cancel_order', 'sign_transaction', 'broadcast_transaction', "
            "'bank_transfer', 'set_live_mode', 'release_kill_switch'"
            ")",
            name="ck_agent_permissions_tool",
        ),
        schema="private",
    )
    op.create_index(
        "ix_agent_permissions_agent_id",
        "agent_permissions",
        ["agent_id"],
        schema="private",
    )
    op.create_table(
        "agent_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("correlation_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["private.agents.id"],
            name="fk_agent_runs_agent_id",
        ),
        sa.UniqueConstraint("idempotency_key", name="uq_agent_runs_idempotency_key"),
        sa.CheckConstraint(
            "status IN ('recorded', 'failed', 'skipped')",
            name="ck_agent_runs_status",
        ),
        sa.CheckConstraint("finished_at >= started_at", name="ck_agent_runs_window"),
        sa.CheckConstraint(
            "char_length(idempotency_key) BETWEEN 1 AND 128",
            name="ck_agent_runs_idempotency",
        ),
        sa.CheckConstraint(
            "char_length(correlation_id) BETWEEN 1 AND 64",
            name="ck_agent_runs_correlation",
        ),
        sa.CheckConstraint(
            "char_length(summary) BETWEEN 1 AND 500",
            name="ck_agent_runs_summary",
        ),
        schema="private",
    )
    op.create_index(
        "ix_agent_runs_agent_started",
        "agent_runs",
        ["agent_id", "started_at"],
        schema="private",
    )
    for agent_id, code, display_name, desk in AGENT_ROWS:
        op.execute(
            sa.text(
                """
                INSERT INTO private.agents (
                    id, code, display_name, desk, status, paper_only,
                    can_submit_orders, can_sign, can_transfer_funds,
                    holds_credentials, notes
                ) VALUES (
                    CAST(:id AS uuid), :code, :display_name, :desk, 'disabled',
                    true, false, false, false, false, :notes
                )
                """
            ).bindparams(
                id=agent_id,
                code=code,
                display_name=display_name,
                desk=desk,
                notes=AGENT_NOTES,
            )
        )
    op.execute(
        sa.text(
            """
            INSERT INTO private.agent_permissions (id, agent_id, tool_name, effect)
            SELECT gen_random_uuid(), agents.id, tools.tool_name, 'deny'
            FROM private.agents AS agents
            CROSS JOIN (
                VALUES
                    ('submit_order'),
                    ('cancel_order'),
                    ('sign_transaction'),
                    ('broadcast_transaction'),
                    ('bank_transfer'),
                    ('set_live_mode'),
                    ('release_kill_switch')
            ) AS tools(tool_name)
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE FUNCTION private.reject_mutation()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                RAISE EXCEPTION 'append-only row';
            END;
            $$
            """
        )
    )
    op.execute(sa.text("REVOKE ALL ON FUNCTION private.reject_mutation() FROM PUBLIC"))
    op.execute(
        sa.text(
            """
            CREATE FUNCTION private.guard_agent_update()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                IF NEW.id IS DISTINCT FROM OLD.id
                   OR NEW.code IS DISTINCT FROM OLD.code
                   OR NEW.paper_only IS DISTINCT FROM OLD.paper_only
                   OR NEW.can_submit_orders IS DISTINCT FROM OLD.can_submit_orders
                   OR NEW.can_sign IS DISTINCT FROM OLD.can_sign
                   OR NEW.can_transfer_funds IS DISTINCT FROM OLD.can_transfer_funds
                   OR NEW.holds_credentials IS DISTINCT FROM OLD.holds_credentials
                   OR NEW.created_at IS DISTINCT FROM OLD.created_at
                THEN
                    RAISE EXCEPTION 'append-only columns on agents';
                END IF;
                RETURN NEW;
            END;
            $$
            """
        )
    )
    op.execute(sa.text("REVOKE ALL ON FUNCTION private.guard_agent_update() FROM PUBLIC"))
    for statement in (
        """
        CREATE TRIGGER agents_no_delete
        BEFORE DELETE ON private.agents
        FOR EACH ROW
        EXECUTE FUNCTION private.reject_mutation()
        """,
        """
        CREATE TRIGGER agents_no_truncate
        BEFORE TRUNCATE ON private.agents
        FOR EACH STATEMENT
        EXECUTE FUNCTION private.reject_mutation()
        """,
        """
        CREATE TRIGGER agents_guard_update
        BEFORE UPDATE ON private.agents
        FOR EACH ROW
        EXECUTE FUNCTION private.guard_agent_update()
        """,
        """
        CREATE TRIGGER agent_permissions_append_only
        BEFORE UPDATE OR DELETE ON private.agent_permissions
        FOR EACH ROW
        EXECUTE FUNCTION private.reject_mutation()
        """,
        """
        CREATE TRIGGER agent_permissions_no_truncate
        BEFORE TRUNCATE ON private.agent_permissions
        FOR EACH STATEMENT
        EXECUTE FUNCTION private.reject_mutation()
        """,
        """
        CREATE TRIGGER agent_runs_append_only
        BEFORE UPDATE OR DELETE ON private.agent_runs
        FOR EACH ROW
        EXECUTE FUNCTION private.reject_mutation()
        """,
        """
        CREATE TRIGGER agent_runs_no_truncate
        BEFORE TRUNCATE ON private.agent_runs
        FOR EACH STATEMENT
        EXECUTE FUNCTION private.reject_mutation()
        """,
        """
        CREATE TRIGGER audit_events_append_only
        BEFORE UPDATE OR DELETE ON public.audit_events
        FOR EACH ROW
        EXECUTE FUNCTION private.reject_mutation()
        """,
        """
        CREATE TRIGGER audit_events_no_truncate
        BEFORE TRUNCATE ON public.audit_events
        FOR EACH STATEMENT
        EXECUTE FUNCTION private.reject_mutation()
        """,
    ):
        op.execute(sa.text(statement))
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])
    op.create_check_constraint(
        "ck_audit_events_correlation_id",
        "audit_events",
        "char_length(correlation_id) BETWEEN 1 AND 64",
    )
    op.create_check_constraint(
        "ck_audit_events_action",
        "audit_events",
        "char_length(action) BETWEEN 1 AND 128",
    )
    for table in ("agents", "agent_permissions", "agent_runs"):
        op.execute(sa.text(f"ALTER TABLE private.{table} ENABLE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"ALTER TABLE private.{table} FORCE ROW LEVEL SECURITY"))
        op.execute(
            sa.text(
                f"""
                CREATE POLICY {table}_local_role ON private.{table}
                FOR ALL
                TO veytrix
                USING (true)
                WITH CHECK (true)
                """
            )
        )
    op.execute(
        sa.text(
            """
            CREATE VIEW public.agent_registry
            WITH (security_invoker = true) AS
            SELECT
                id,
                code,
                display_name,
                desk,
                status,
                paper_only,
                can_submit_orders,
                can_sign,
                can_transfer_funds,
                holds_credentials,
                notes,
                created_at
            FROM private.agents
            """
        )
    )
    op.execute(sa.text("REVOKE ALL ON public.agent_registry FROM PUBLIC"))


def downgrade() -> None:
    op.execute(sa.text("DROP VIEW IF EXISTS public.agent_registry"))
    for statement in (
        "DROP TRIGGER IF EXISTS audit_events_no_truncate ON public.audit_events",
        "DROP TRIGGER IF EXISTS audit_events_append_only ON public.audit_events",
        "DROP TRIGGER IF EXISTS agent_runs_no_truncate ON private.agent_runs",
        "DROP TRIGGER IF EXISTS agent_runs_append_only ON private.agent_runs",
        "DROP TRIGGER IF EXISTS agent_permissions_no_truncate ON private.agent_permissions",
        "DROP TRIGGER IF EXISTS agent_permissions_append_only ON private.agent_permissions",
        "DROP TRIGGER IF EXISTS agents_guard_update ON private.agents",
        "DROP TRIGGER IF EXISTS agents_no_truncate ON private.agents",
        "DROP TRIGGER IF EXISTS agents_no_delete ON private.agents",
    ):
        op.execute(sa.text(statement))
    op.execute(sa.text("DROP FUNCTION IF EXISTS private.guard_agent_update()"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS private.reject_mutation()"))
    op.drop_constraint("ck_audit_events_action", "audit_events", type_="check")
    op.drop_constraint("ck_audit_events_correlation_id", "audit_events", type_="check")
    op.drop_index("ix_audit_events_created_at", table_name="audit_events")
    op.drop_index("ix_agent_runs_agent_started", table_name="agent_runs", schema="private")
    op.drop_table("agent_runs", schema="private")
    op.drop_index(
        "ix_agent_permissions_agent_id",
        table_name="agent_permissions",
        schema="private",
    )
    op.drop_table("agent_permissions", schema="private")
    op.drop_table("agents", schema="private")
    op.execute(sa.text("DROP SCHEMA IF EXISTS private"))
