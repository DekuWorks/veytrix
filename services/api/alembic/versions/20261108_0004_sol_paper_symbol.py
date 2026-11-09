"""Allow SOL-USD on a saved paper size. Still not a fill.

Revision ID: 0004_sol_paper_symbol
Revises: 0003_research_notes
Create Date: 2026-11-08
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0004_sol_paper_symbol"
down_revision: str | None = "0003_research_notes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ALLOWED = "symbol IN ('BTC-USD', 'ETH-USD', 'SOL-USD')"
_PREVIOUS = "symbol IN ('BTC-USD', 'ETH-USD')"


def upgrade() -> None:
    op.drop_constraint("ck_paper_positions_symbol", "paper_positions", type_="check")
    op.create_check_constraint("ck_paper_positions_symbol", "paper_positions", _ALLOWED)


def downgrade() -> None:
    op.drop_constraint("ck_paper_positions_symbol", "paper_positions", type_="check")
    op.create_check_constraint("ck_paper_positions_symbol", "paper_positions", _PREVIOUS)
