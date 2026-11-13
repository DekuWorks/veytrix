"""Research assignments from Roads. Not an order path.

A row records who was asked, the subject, and the message that answered.
Status may move from assigned to reported or blocked. It cannot submit,
sign, or transfer. Messages stay append-only in their own table.

Revision ID: 0013_research_tasks
Revises: 0012_enable_registry_status
Create Date: 2026-11-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013_research_tasks"
down_revision: str | None = "0012_enable_registry_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CODES = (
    "'SUPERVISOR-01', 'DAY-01', 'STOCK-01', 'CRYPTO-01', 'DEFI-01', "
    "'ETF-01', 'FUTURES-01', 'RESEARCH-01', 'RISK-01', 'TREASURY-01'"
)


def upgrade() -> None:
    op.create_table(
        "research_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("assignee_code", sa.String(length=32), nullable=False),
        sa.Column("assigned_by", sa.String(length=32), nullable=False),
        sa.Column("subject", sa.String(length=80), nullable=False),
        sa.Column("instruction", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("evidence_message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(f"assignee_code IN ({CODES})", name="ck_research_tasks_assignee"),
        sa.CheckConstraint("assigned_by = 'SUPERVISOR-01'", name="ck_research_tasks_assigner"),
        sa.CheckConstraint(
            "status IN ('assigned', 'reported', 'blocked')",
            name="ck_research_tasks_status",
        ),
        sa.CheckConstraint(
            "char_length(subject) BETWEEN 1 AND 80",
            name="ck_research_tasks_subject",
        ),
        sa.CheckConstraint(
            "char_length(instruction) BETWEEN 1 AND 500",
            name="ck_research_tasks_instruction",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["private.conversations.id"],
            name="fk_research_tasks_conversation",
        ),
        schema="private",
    )
    op.create_index(
        "ix_research_tasks_assignee",
        "research_tasks",
        ["assignee_code", "created_at"],
        schema="private",
    )
    op.execute(sa.text("ALTER TABLE private.research_tasks ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text("ALTER TABLE private.research_tasks FORCE ROW LEVEL SECURITY"))
    op.execute(
        sa.text(
            """
            CREATE POLICY research_tasks_local_role ON private.research_tasks
            FOR ALL
            TO veytrix
            USING (true)
            WITH CHECK (true)
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS private.research_tasks CASCADE"))
