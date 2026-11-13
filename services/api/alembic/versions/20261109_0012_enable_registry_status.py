"""Let each desk be enabled for paper research. Trading rights stay denied.

`status` is not a trading flag. `can_submit_orders`, `can_sign`,
`can_transfer_funds`, and `holds_credentials` stay false. This revision does
not add an order route and does not call a broker.

Revision ID: 0012_enable_registry_status
Revises: 0011_agent_comms
Create Date: 2026-11-09
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_enable_registry_status"
down_revision: str | None = "0011_agent_comms"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PAPER_NOTE = (
    "Enabled for paper research and coordination. Cannot submit an order, "
    "sign a transaction, or move funds."
)
FUTURES_NOTE = (
    "Enabled for futures research only. Topstep automation is off and no account "
    "is connected. Cannot submit an order, sign, or move funds."
)
DISABLED_NOTE = (
    "Registry row only. This desk is not running. It cannot submit an order, "
    "sign a transaction, or move funds."
)


def upgrade() -> None:
    op.drop_constraint("ck_agents_status", "agents", schema="private", type_="check")
    op.create_check_constraint(
        "ck_agents_status",
        "agents",
        "status IN ('disabled', 'paused', 'enabled')",
        schema="private",
    )
    op.execute(
        sa.text(
            "UPDATE private.agents SET status = 'enabled', notes = :note "
            "WHERE status = 'disabled' AND code <> 'FUTURES-01'"
        ).bindparams(note=PAPER_NOTE)
    )
    op.execute(
        sa.text(
            "UPDATE private.agents SET status = 'enabled', notes = :note "
            "WHERE status = 'disabled' AND code = 'FUTURES-01'"
        ).bindparams(note=FUTURES_NOTE)
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE private.agents SET status = 'disabled', notes = :note WHERE status = 'enabled'"
        ).bindparams(note=DISABLED_NOTE)
    )
    op.drop_constraint("ck_agents_status", "agents", schema="private", type_="check")
    op.create_check_constraint(
        "ck_agents_status",
        "agents",
        "status IN ('disabled', 'paused')",
        schema="private",
    )
