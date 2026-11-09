"""Add a disabled FUTURES-01 desk. It cannot trade or call Topstep.

Revision ID: 0010_futures_desk
Revises: 0009_agent_registry
Create Date: 2026-11-09
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_futures_desk"
down_revision: str | None = "0009_agent_registry"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FUTURES_ID = "a100000a-0000-4000-8000-00000000000a"
FUTURES_NOTES = (
    "Registry row only. FUTURES-01 is not running. Topstep automation is disabled. "
    "This desk cannot submit an order, sign a transaction, or move funds."
)
CODES = (
    "'SUPERVISOR-01', 'DAY-01', 'STOCK-01', 'CRYPTO-01', 'DEFI-01', "
    "'ETF-01', 'FUTURES-01', 'RESEARCH-01', 'RISK-01', 'TREASURY-01'"
)


def upgrade() -> None:
    op.execute(sa.text("ALTER TABLE private.agents DROP CONSTRAINT ck_agents_code"))
    op.execute(
        sa.text(
            f"ALTER TABLE private.agents ADD CONSTRAINT ck_agents_code CHECK (code IN ({CODES}))"
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO private.agents (
                id, code, display_name, desk, status, paper_only,
                can_submit_orders, can_sign, can_transfer_funds,
                holds_credentials, notes
            ) VALUES (
                CAST(:id AS uuid), 'FUTURES-01', 'Futures desk', 'futures-research',
                'disabled', true, false, false, false, false, :notes
            )
            """
        ).bindparams(id=FUTURES_ID, notes=FUTURES_NOTES)
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
            WHERE agents.code = 'FUTURES-01'
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "ALTER TABLE private.agent_permissions DISABLE TRIGGER agent_permissions_append_only"
        )
    )
    op.execute(sa.text("ALTER TABLE private.agents DISABLE TRIGGER agents_no_delete"))
    op.execute(
        sa.text(
            "DELETE FROM private.agent_permissions WHERE agent_id = CAST(:id AS uuid)"
        ).bindparams(id=FUTURES_ID)
    )
    op.execute(sa.text("DELETE FROM private.agents WHERE code = 'FUTURES-01'"))
    op.execute(
        sa.text(
            "ALTER TABLE private.agent_permissions ENABLE TRIGGER agent_permissions_append_only"
        )
    )
    op.execute(sa.text("ALTER TABLE private.agents ENABLE TRIGGER agents_no_delete"))
    op.execute(sa.text("ALTER TABLE private.agents DROP CONSTRAINT ck_agents_code"))
    op.execute(
        sa.text(
            "ALTER TABLE private.agents ADD CONSTRAINT ck_agents_code CHECK (code IN ("
            "'SUPERVISOR-01', 'DAY-01', 'STOCK-01', 'CRYPTO-01', 'DEFI-01', "
            "'ETF-01', 'RESEARCH-01', 'RISK-01', 'TREASURY-01'))"
        )
    )
