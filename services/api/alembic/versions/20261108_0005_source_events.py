"""Source events the user typed. Not a fetch and not an order.

Revision ID: 0005_source_events
Revises: 0004_sol_paper_symbol
Create Date: 2026-11-08
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_source_events"
down_revision: str | None = "0004_sol_paper_symbol"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "source_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("source", sa.String(length=200), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_public_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(title) BETWEEN 1 AND 120",
            name="ck_source_events_title",
        ),
        sa.CheckConstraint(
            "char_length(source) BETWEEN 1 AND 200",
            name="ck_source_events_source",
        ),
    )


def downgrade() -> None:
    op.drop_table("source_events")
