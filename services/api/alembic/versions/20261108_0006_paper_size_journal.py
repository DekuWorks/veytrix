"""Paper size journal. A successful paper calculation, not an order.

Revision ID: 0006_paper_size_journal
Revises: 0005_source_events
Create Date: 2026-11-08
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_paper_size_journal"
down_revision: str | None = "0005_source_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "paper_size_journal",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("equity", sa.Numeric(24, 8), nullable=False),
        sa.Column("entry", sa.Numeric(24, 8), nullable=False),
        sa.Column("stop", sa.Numeric(24, 8), nullable=False),
        sa.Column("shares", sa.Integer(), nullable=False),
        sa.Column("planned_risk", sa.Numeric(24, 8), nullable=False),
        sa.Column("binding_constraint", sa.String(length=16), nullable=False),
        sa.Column("execution_permitted", sa.Boolean(), nullable=False),
        sa.Column("order_submitted", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "symbol IN ('BTC-USD', 'ETH-USD', 'SOL-USD')",
            name="ck_paper_size_journal_symbol",
        ),
        sa.CheckConstraint("equity > 0", name="ck_paper_size_journal_equity"),
        sa.CheckConstraint("entry > 0", name="ck_paper_size_journal_entry"),
        sa.CheckConstraint("stop > 0", name="ck_paper_size_journal_stop"),
        sa.CheckConstraint("stop < entry", name="ck_paper_size_journal_long_stop"),
        sa.CheckConstraint("shares >= 0", name="ck_paper_size_journal_shares"),
        sa.CheckConstraint("planned_risk >= 0", name="ck_paper_size_journal_planned_risk"),
        sa.CheckConstraint(
            "binding_constraint IN ('risk', 'allocation', 'both', 'none')",
            name="ck_paper_size_journal_binding",
        ),
        sa.CheckConstraint(
            "execution_permitted = false AND order_submitted = false",
            name="ck_paper_size_journal_not_an_order",
        ),
    )


def downgrade() -> None:
    op.drop_table("paper_size_journal")
