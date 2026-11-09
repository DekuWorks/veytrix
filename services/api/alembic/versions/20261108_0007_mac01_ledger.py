"""MAC-01 ledger. Signals, Alpaca Trading API orders (paper or live), one control row.

Revision ID: 0007_mac01_ledger
Revises: 0006_paper_size_journal
Create Date: 2026-11-08
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_mac01_ledger"
down_revision: str | None = "0006_paper_size_journal"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mac01_signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("strategy_version", sa.String(length=32), nullable=False),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("session_date", sa.Date(), nullable=False),
        sa.Column("close", sa.Numeric(24, 8), nullable=False),
        sa.Column("fast_prev", sa.Numeric(24, 8), nullable=False),
        sa.Column("slow_prev", sa.Numeric(24, 8), nullable=False),
        sa.Column("fast_cur", sa.Numeric(24, 8), nullable=False),
        sa.Column("slow_cur", sa.Numeric(24, 8), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("reason", sa.String(length=200), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("decision_reason", sa.String(length=300), nullable=False),
        sa.Column("inputs_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "decided_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "strategy_version", "symbol", "session_date", name="uq_mac01_signals_session"
        ),
        sa.CheckConstraint("symbol = 'AAPL'", name="ck_mac01_signals_symbol"),
        sa.CheckConstraint("side IN ('BUY', 'SELL', 'HOLD')", name="ck_mac01_signals_side"),
    )
    op.create_table(
        "mac01_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("client_order_id", sa.String(length=128), nullable=False),
        sa.Column("mode", sa.String(length=8), nullable=False),
        sa.Column("strategy_version", sa.String(length=32), nullable=False),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("session_date", sa.Date(), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("notional", sa.Numeric(24, 2), nullable=True),
        sa.Column("qty", sa.Numeric(24, 9), nullable=True),
        sa.Column("order_type", sa.String(length=16), nullable=False),
        sa.Column("time_in_force", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("broker_order_id", sa.String(length=64), nullable=True),
        sa.Column("filled_qty", sa.Numeric(24, 9), nullable=False),
        sa.Column("filled_avg_price", sa.Numeric(24, 8), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.UniqueConstraint("client_order_id", name="uq_mac01_orders_client_order_id"),
        sa.CheckConstraint("symbol = 'AAPL'", name="ck_mac01_orders_symbol"),
        sa.CheckConstraint("mode IN ('paper', 'live')", name="ck_mac01_orders_mode"),
        sa.CheckConstraint(
            "(side = 'buy' AND notional IS NOT NULL AND qty IS NULL "
            "AND notional > 0 AND notional <= 100) "
            "OR (side = 'sell' AND qty IS NOT NULL AND notional IS NULL AND qty > 0)",
            name="ck_mac01_orders_sizing",
        ),
        sa.CheckConstraint("filled_qty >= 0", name="ck_mac01_orders_filled"),
        sa.CheckConstraint("order_type = 'market'", name="ck_mac01_orders_type"),
        sa.CheckConstraint("time_in_force = 'day'", name="ck_mac01_orders_tif"),
    )
    op.create_table(
        "mac01_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("paused", sa.Boolean(), nullable=False),
        sa.Column("kill_switch", sa.Boolean(), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_status", sa.String(length=32), nullable=True),
        sa.Column("last_run_message", sa.String(length=500), nullable=True),
        sa.Column("last_session_date", sa.Date(), nullable=True),
        sa.Column("last_mode", sa.String(length=8), nullable=True),
        sa.Column("position_qty", sa.Numeric(24, 9), nullable=True),
        sa.Column("position_avg_entry_price", sa.Numeric(24, 8), nullable=True),
        sa.Column("position_market_price", sa.Numeric(24, 8), nullable=True),
        sa.Column("position_unrealised_pl", sa.Numeric(24, 8), nullable=True),
        sa.Column("position_as_of", sa.DateTime(timezone=True), nullable=True),
        sa.Column("chart", postgresql.JSONB(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("id = 1", name="ck_mac01_state_singleton"),
    )
    op.execute("INSERT INTO mac01_state (id, paused, kill_switch) VALUES (1, false, false)")


def downgrade() -> None:
    op.drop_table("mac01_state")
    op.drop_table("mac01_orders")
    op.drop_table("mac01_signals")
