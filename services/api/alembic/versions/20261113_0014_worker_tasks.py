"""Research task states, worker heartbeats, and a model-call ledger.

Status moves from the old assigned/reported pair to queued, running, blocked,
completed, and failed. Completed requires an evidence message. Heartbeats are
a column on agent_presence, not a second presence table. Nothing here grants
a trading right.

Revision ID: 0014_worker_tasks
Revises: 0013_research_tasks
Create Date: 2026-11-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014_worker_tasks"
down_revision: str | None = "0013_research_tasks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_STATUS = "status IN ('queued', 'running', 'blocked', 'completed', 'failed')"
OLD_STATUS = "status IN ('assigned', 'reported', 'blocked')"
LIFECYCLE = "lifecycle IN ('idle', 'queued', 'working', 'blocked', 'offline', 'failed')"


def upgrade() -> None:
    op.drop_constraint(
        "ck_research_tasks_status", "research_tasks", schema="private", type_="check"
    )
    op.execute(
        sa.text(
            """
            UPDATE private.research_tasks
            SET status = 'queued'
            WHERE status = 'assigned'
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE private.research_tasks
            SET status = 'blocked'
            WHERE status = 'reported'
            """
        )
    )
    op.add_column(
        "research_tasks",
        sa.Column("kind", sa.String(length=16), nullable=False, server_default="research"),
        schema="private",
    )
    op.add_column(
        "research_tasks",
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        schema="private",
    )
    op.add_column(
        "research_tasks",
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="2"),
        schema="private",
    )
    op.add_column(
        "research_tasks",
        sa.Column("worker_id", sa.String(length=64), nullable=True),
        schema="private",
    )
    op.add_column(
        "research_tasks",
        sa.Column("blocked_reason", sa.String(length=200), nullable=True),
        schema="private",
    )
    op.add_column(
        "research_tasks",
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        schema="private",
    )
    op.execute(
        sa.text(
            """
            UPDATE private.research_tasks
            SET blocked_reason = 'no_stored_source'
            WHERE status = 'blocked' AND blocked_reason IS NULL
            """
        )
    )
    op.create_check_constraint(
        "ck_research_tasks_status",
        "research_tasks",
        NEW_STATUS,
        schema="private",
    )
    op.create_check_constraint(
        "ck_research_tasks_kind",
        "research_tasks",
        "kind IN ('research', 'review')",
        schema="private",
    )
    op.create_check_constraint(
        "ck_research_tasks_attempts",
        "research_tasks",
        "attempt_count BETWEEN 0 AND 3 AND max_attempts BETWEEN 1 AND 3",
        schema="private",
    )
    op.create_check_constraint(
        "ck_research_tasks_completed_needs_evidence",
        "research_tasks",
        "status <> 'completed' OR evidence_message_id IS NOT NULL",
        schema="private",
    )
    op.create_index(
        "ix_research_tasks_status",
        "research_tasks",
        ["status", "created_at"],
        schema="private",
    )

    op.add_column(
        "agent_presence",
        sa.Column("lifecycle", sa.String(length=16), nullable=False, server_default="offline"),
        schema="private",
    )
    op.add_column(
        "agent_presence",
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        schema="private",
    )
    op.add_column(
        "agent_presence",
        sa.Column("worker_id", sa.String(length=64), nullable=True),
        schema="private",
    )
    op.add_column(
        "agent_presence",
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema="private",
    )
    op.create_check_constraint(
        "ck_presence_lifecycle",
        "agent_presence",
        LIFECYCLE,
        schema="private",
    )

    op.create_table(
        "task_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("body", sa.String(length=500), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('state', 'chunk', 'retry', 'heartbeat')", name="ck_task_events_kind"
        ),
        sa.CheckConstraint("char_length(body) BETWEEN 1 AND 500", name="ck_task_events_body"),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["private.research_tasks.id"],
            name="fk_task_events_task",
        ),
        schema="private",
    )
    op.create_index(
        "ix_task_events_task", "task_events", ["task_id", "created_at"], schema="private"
    )

    op.create_table(
        "model_calls",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_code", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("provider_message_id", sa.String(length=80), nullable=True),
        sa.Column("estimated_usd", sa.Numeric(6, 4), nullable=False, server_default="0"),
        sa.Column("error_class", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("estimated_usd >= 0", name="ck_model_calls_spend"),
        schema="private",
    )
    op.create_index("ix_model_calls_created", "model_calls", ["created_at"], schema="private")

    for table in ("task_events", "model_calls"):
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

    for verb, level in (("update", "ROW"), ("delete", "ROW"), ("truncate", "STATEMENT")):
        op.execute(
            sa.text(
                f"""
                CREATE TRIGGER task_events_no_{verb}
                BEFORE {verb.upper()} ON private.task_events
                FOR EACH {level}
                EXECUTE FUNCTION private.reject_mutation()
                """
            )
        )


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS private.model_calls CASCADE"))
    op.execute(sa.text("DROP TABLE IF EXISTS private.task_events CASCADE"))
    op.drop_constraint("ck_presence_lifecycle", "agent_presence", schema="private", type_="check")
    op.drop_column("agent_presence", "task_id", schema="private")
    op.drop_column("agent_presence", "worker_id", schema="private")
    op.drop_column("agent_presence", "heartbeat_at", schema="private")
    op.drop_column("agent_presence", "lifecycle", schema="private")
    op.drop_index("ix_research_tasks_status", table_name="research_tasks", schema="private")
    op.drop_constraint(
        "ck_research_tasks_completed_needs_evidence",
        "research_tasks",
        schema="private",
        type_="check",
    )
    op.drop_constraint(
        "ck_research_tasks_attempts", "research_tasks", schema="private", type_="check"
    )
    op.drop_constraint("ck_research_tasks_kind", "research_tasks", schema="private", type_="check")
    op.drop_constraint(
        "ck_research_tasks_status", "research_tasks", schema="private", type_="check"
    )
    op.execute(
        sa.text(
            """
            UPDATE private.research_tasks
            SET status = CASE status
                WHEN 'queued' THEN 'assigned'
                WHEN 'running' THEN 'assigned'
                WHEN 'completed' THEN 'reported'
                ELSE 'blocked'
            END
            """
        )
    )
    op.drop_column("research_tasks", "correlation_id", schema="private")
    op.drop_column("research_tasks", "blocked_reason", schema="private")
    op.drop_column("research_tasks", "worker_id", schema="private")
    op.drop_column("research_tasks", "max_attempts", schema="private")
    op.drop_column("research_tasks", "attempt_count", schema="private")
    op.drop_column("research_tasks", "kind", schema="private")
    op.create_check_constraint(
        "ck_research_tasks_status",
        "research_tasks",
        OLD_STATUS,
        schema="private",
    )
