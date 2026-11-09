"""Baseline paper schema. One experimental policy and no prices.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-11-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

POLICY_ID = "6f0c1a2e-7b34-4c2a-9d11-0a1b2c3d4e5f"
POLICY_NOTES = (
    "Experimental paper policy. Daily and weekly stops are stored and are not "
    "enforced against a ledger. Stops can fail. This row is not investment advice "
    "and does not permit an order."
)


def upgrade() -> None:
    op.create_table(
        "instruments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("asset_type", sa.String(length=32), nullable=False),
        sa.Column("venue", sa.String(length=32), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("contract_multiplier", sa.Numeric(24, 8), nullable=False),
        sa.Column("tick_size", sa.Numeric(24, 8), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("calendar", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("venue", "symbol", name="uq_instruments_venue_symbol"),
    )
    op.create_table(
        "price_bars",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("instrument_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bar_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Numeric(24, 8), nullable=False),
        sa.Column("high", sa.Numeric(24, 8), nullable=False),
        sa.Column("low", sa.Numeric(24, 8), nullable=False),
        sa.Column("close", sa.Numeric(24, 8), nullable=False),
        sa.Column("volume", sa.Numeric(24, 4), nullable=False),
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            name="fk_price_bars_instrument_id",
        ),
        sa.UniqueConstraint(
            "instrument_id",
            "bar_start",
            name="uq_price_bars_instrument_bar_start",
        ),
        sa.CheckConstraint(
            "high >= low AND high >= open AND high >= close AND low <= open AND low <= close",
            name="ck_price_bars_ohlc",
        ),
        sa.CheckConstraint("volume >= 0", name="ck_price_bars_volume"),
        sa.CheckConstraint(
            "open > 0 AND high > 0 AND low > 0 AND close > 0",
            name="ck_price_bars_positive",
        ),
    )
    op.create_table(
        "risk_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("experimental", sa.Boolean(), nullable=False),
        sa.Column("trading_mode", sa.String(length=16), nullable=False),
        sa.Column("per_trade_risk_fraction", sa.Numeric(8, 6), nullable=False),
        sa.Column("daily_loss_stop_fraction", sa.Numeric(8, 6), nullable=False),
        sa.Column("weekly_loss_stop_fraction", sa.Numeric(8, 6), nullable=False),
        sa.Column("max_allocation_fraction", sa.Numeric(8, 6), nullable=False),
        sa.Column("risk_fraction_ceiling", sa.Numeric(8, 6), nullable=False),
        sa.Column("daily_stop_enforced", sa.Boolean(), nullable=False),
        sa.Column("weekly_stop_enforced", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("name", name="uq_risk_policies_name"),
        sa.CheckConstraint("trading_mode = 'paper'", name="ck_risk_policies_paper_only"),
        sa.CheckConstraint("experimental", name="ck_risk_policies_experimental"),
        sa.CheckConstraint(
            "daily_stop_enforced = false AND weekly_stop_enforced = false",
            name="ck_risk_policies_stops_not_enforced",
        ),
        sa.CheckConstraint(
            "per_trade_risk_fraction > 0 AND per_trade_risk_fraction <= 0.02",
            name="ck_risk_policies_per_trade",
        ),
        sa.CheckConstraint(
            "daily_loss_stop_fraction > 0 AND daily_loss_stop_fraction <= 0.02",
            name="ck_risk_policies_daily",
        ),
        sa.CheckConstraint(
            "weekly_loss_stop_fraction > 0 AND weekly_loss_stop_fraction <= 0.05",
            name="ck_risk_policies_weekly",
        ),
        sa.CheckConstraint(
            "max_allocation_fraction > 0 AND max_allocation_fraction <= 0.10",
            name="ck_risk_policies_allocation",
        ),
        sa.CheckConstraint("risk_fraction_ceiling = 0.02", name="ck_risk_policies_ceiling"),
    )
    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_audit_events_correlation_id", "audit_events", ["correlation_id"])
    op.execute(
        sa.text(
            """
            INSERT INTO risk_policies (
                id,
                name,
                experimental,
                trading_mode,
                per_trade_risk_fraction,
                daily_loss_stop_fraction,
                weekly_loss_stop_fraction,
                max_allocation_fraction,
                risk_fraction_ceiling,
                daily_stop_enforced,
                weekly_stop_enforced,
                notes
            ) VALUES (
                CAST(:id AS uuid),
                :name,
                true,
                'paper',
                0.005,
                0.01,
                0.03,
                0.10,
                0.02,
                false,
                false,
                :notes
            )
            """
        ).bindparams(
            id=POLICY_ID,
            name="experimental-paper-default",
            notes=POLICY_NOTES,
        )
    )


def downgrade() -> None:
    op.drop_index("ix_audit_events_correlation_id", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_table("price_bars")
    op.drop_table("risk_policies")
    op.drop_table("instruments")
