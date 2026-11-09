"""Research notes. A saved note, not an instruction to trade.

Revision ID: 0003_research_notes
Revises: 0002_paper_positions
Create Date: 2026-11-08
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_research_notes"
down_revision: str | None = "0002_paper_positions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(title) BETWEEN 1 AND 120",
            name="ck_research_notes_title",
        ),
        sa.CheckConstraint(
            "char_length(body) BETWEEN 1 AND 4000",
            name="ck_research_notes_body",
        ),
    )


def downgrade() -> None:
    op.drop_table("research_notes")
