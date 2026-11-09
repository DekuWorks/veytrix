"""Paper positions. A saved size, not a fill.

Revision ID: 0002_paper_positions
Revises: 0001_baseline
Create Date: 2026-11-08
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_paper_positions"
down_revision: str | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "paper_positions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("entry", sa.Numeric(24, 8), nullable=False),
        sa.Column("stop", sa.Numeric(24, 8), nullable=False),
        sa.Column("shares", sa.Integer(), nullable=False),
        sa.Column("notional", sa.Numeric(24, 8), nullable=False),
        sa.Column("planned_risk", sa.Numeric(24, 8), nullable=False),
        sa.Column("binding_constraint", sa.String(length=16), nullable=False),
        sa.Column("exchange_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "symbol IN ('BTC-USD', 'ETH-USD')",
            name="ck_paper_positions_symbol",
        ),
        sa.CheckConstraint("entry > 0", name="ck_paper_positions_entry"),
        sa.CheckConstraint("stop > 0", name="ck_paper_positions_stop"),
        sa.CheckConstraint("shares >= 0", name="ck_paper_positions_shares"),
        sa.CheckConstraint("notional >= 0", name="ck_paper_positions_notional"),
        sa.CheckConstraint("planned_risk >= 0", name="ck_paper_positions_planned_risk"),
        sa.CheckConstraint(
            "binding_constraint IN ('risk', 'allocation', 'both', 'none')",
            name="ck_paper_positions_binding",
        ),
    )


def downgrade() -> None:
    op.drop_table("paper_positions")
