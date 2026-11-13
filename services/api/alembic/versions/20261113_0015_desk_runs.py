"""Paper desk runs, local fills, alert acknowledgements, and signal audits.

A fill is a simulated ledger row. execution_permitted and order_submitted
stay false. An acknowledgement does not change a research task.

Revision ID: 0015_desk_runs
Revises: 0014_worker_tasks
Create Date: 2026-11-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015_desk_runs"
down_revision: str | None = "0014_worker_tasks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "desk_runs",
        sa.Column("agent_code", sa.String(length=32), primary_key=True),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("block_reason", sa.String(length=80), nullable=True),
        sa.Column("paper_fill_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("worker_id", sa.String(length=64), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "state IN ('active', 'idle', 'blocked', 'failed')",
            name="ck_desk_runs_state",
        ),
        sa.CheckConstraint("char_length(source_id) BETWEEN 1 AND 64", name="ck_desk_runs_source"),
        schema="private",
    )
    op.create_table(
        "paper_fills",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_code", sa.String(length=32), nullable=False),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("price", sa.Numeric(24, 8), nullable=False),
        sa.Column("quantity", sa.Numeric(24, 8), nullable=False),
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("bar_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("execution_permitted", sa.Boolean(), nullable=False),
        sa.Column("order_submitted", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("symbol = 'BTC-USD'", name="ck_paper_fills_symbol"),
        sa.CheckConstraint("price > 0", name="ck_paper_fills_price"),
        sa.CheckConstraint("quantity > 0", name="ck_paper_fills_quantity"),
        sa.CheckConstraint(
            "execution_permitted = false AND order_submitted = false",
            name="ck_paper_fills_not_a_broker_order",
        ),
        sa.CheckConstraint("source_id = 'coinbase-exchange'", name="ck_paper_fills_source"),
        sa.UniqueConstraint("symbol", "bar_start", name="uq_paper_fills_bar"),
        schema="private",
    )
    op.create_table(
        "alert_acks",
        sa.Column("task_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("acked_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["private.research_tasks.id"],
            name="fk_alert_acks_task",
        ),
        schema="private",
    )
    op.create_table(
        "signal_audits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("detail", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "provider IN ('traderspost', 'signalstack')",
            name="ck_signal_audits_provider",
        ),
        sa.CheckConstraint(
            "outcome IN ("
            "'rejected_disabled', 'rejected_route', 'rejected_payload', "
            "'rejected_duplicate', 'rejected_timeout', 'rejected_broker'"
            ")",
            name="ck_signal_audits_outcome",
        ),
        sa.UniqueConstraint("fingerprint", name="uq_signal_audits_fingerprint"),
        schema="private",
    )
    for table in ("desk_runs", "paper_fills", "alert_acks", "signal_audits"):
        op.execute(sa.text(f"ALTER TABLE private.{table} ENABLE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"ALTER TABLE private.{table} FORCE ROW LEVEL SECURITY"))
        op.execute(
            sa.text(
                f"""
                CREATE POLICY {table}_local_role ON private.{table}
                FOR ALL TO veytrix USING (true) WITH CHECK (true)
                """
            )
        )


def downgrade() -> None:
    for table in ("signal_audits", "alert_acks", "paper_fills", "desk_runs"):
        op.execute(sa.text(f"DROP TABLE IF EXISTS private.{table} CASCADE"))
