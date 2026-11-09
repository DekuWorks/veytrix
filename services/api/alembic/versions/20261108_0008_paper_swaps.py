"""Simulated paper swaps. Balances and fills only. No keys.

Revision ID: 0008_paper_swaps
Revises: 0007_mac01_ledger
Create Date: 2026-11-08
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_paper_swaps"
down_revision: str | None = "0007_mac01_ledger"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "blockchain_networks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=16), nullable=False),
        sa.Column("network", sa.String(length=32), nullable=False),
        sa.Column("chain_id", sa.String(length=16), nullable=False),
        sa.Column("simulated", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("name", name="uq_blockchain_networks_name"),
        sa.CheckConstraint(
            "name IN ('solana', 'ethereum', 'base')",
            name="ck_blockchain_networks_name",
        ),
        sa.CheckConstraint(
            "network IN ('solana-devnet', 'sepolia', 'base-sepolia')",
            name="ck_blockchain_networks_network",
        ),
        sa.CheckConstraint(
            "chain_id IN ('devnet', '11155111', '84532')",
            name="ck_blockchain_networks_chain",
        ),
        sa.CheckConstraint("simulated", name="ck_blockchain_networks_simulated"),
    )
    op.create_table(
        "simulated_wallet_balances",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("network_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("amount", sa.Numeric(36, 18), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["network_id"],
            ["blockchain_networks.id"],
            name="fk_simulated_wallet_balances_network_id",
        ),
        sa.UniqueConstraint(
            "network_id", "symbol", name="uq_simulated_wallet_balances_network_symbol"
        ),
        sa.CheckConstraint("amount >= 0", name="ck_simulated_wallet_balances_amount"),
    )
    op.create_table(
        "paper_swap_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("network_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_in", sa.String(length=16), nullable=False),
        sa.Column("token_out", sa.String(length=16), nullable=False),
        sa.Column("amount_in", sa.Numeric(36, 18), nullable=False),
        sa.Column("quoted_out", sa.Numeric(36, 18), nullable=False),
        sa.Column("amount_out", sa.Numeric(36, 18), nullable=False),
        sa.Column("quoted_price", sa.Numeric(36, 18), nullable=False),
        sa.Column("slippage_bps", sa.Integer(), nullable=False),
        sa.Column("slippage_applied", sa.Numeric(36, 18), nullable=False),
        sa.Column("fee_estimate", sa.Numeric(36, 18), nullable=False),
        sa.Column("fee_symbol", sa.String(length=16), nullable=False),
        sa.Column("quote_source", sa.String(length=64), nullable=False),
        sa.Column("price_kind", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("simulated", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["network_id"],
            ["blockchain_networks.id"],
            name="fk_paper_swap_orders_network_id",
        ),
        sa.CheckConstraint("status = 'simulated'", name="ck_paper_swap_orders_status"),
        sa.CheckConstraint("simulated", name="ck_paper_swap_orders_simulated"),
        sa.CheckConstraint("amount_in > 0", name="ck_paper_swap_orders_amount_in"),
        sa.CheckConstraint("quoted_out > 0", name="ck_paper_swap_orders_quoted_out"),
        sa.CheckConstraint("amount_out > 0", name="ck_paper_swap_orders_amount_out"),
        sa.CheckConstraint("quoted_price > 0", name="ck_paper_swap_orders_price"),
        sa.CheckConstraint("slippage_bps BETWEEN 1 AND 500", name="ck_paper_swap_orders_slippage"),
        sa.CheckConstraint("slippage_applied >= 0", name="ck_paper_swap_orders_slippage_applied"),
        sa.CheckConstraint("fee_estimate >= 0", name="ck_paper_swap_orders_fee"),
        sa.CheckConstraint(
            "price_kind IN ('pool', 'reference')",
            name="ck_paper_swap_orders_price_kind",
        ),
    )
    op.create_table(
        "paper_swap_fills",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount_in", sa.Numeric(36, 18), nullable=False),
        sa.Column("amount_out", sa.Numeric(36, 18), nullable=False),
        sa.Column("fee_estimate", sa.Numeric(36, 18), nullable=False),
        sa.Column("slippage_applied", sa.Numeric(36, 18), nullable=False),
        sa.Column("quoted_price", sa.Numeric(36, 18), nullable=False),
        sa.Column("quote_source", sa.String(length=64), nullable=False),
        sa.Column("simulated", sa.Boolean(), nullable=False),
        sa.Column("balances_after", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["paper_swap_orders.id"],
            name="fk_paper_swap_fills_order_id",
        ),
        sa.UniqueConstraint("order_id", name="uq_paper_swap_fills_order_id"),
        sa.CheckConstraint("simulated", name="ck_paper_swap_fills_simulated"),
        sa.CheckConstraint("amount_in > 0", name="ck_paper_swap_fills_amount_in"),
        sa.CheckConstraint("amount_out > 0", name="ck_paper_swap_fills_amount_out"),
        sa.CheckConstraint("fee_estimate >= 0", name="ck_paper_swap_fills_fee"),
        sa.CheckConstraint("slippage_applied >= 0", name="ck_paper_swap_fills_slippage"),
        sa.CheckConstraint("quoted_price > 0", name="ck_paper_swap_fills_price"),
    )


def downgrade() -> None:
    op.drop_table("paper_swap_fills")
    op.drop_table("paper_swap_orders")
    op.drop_table("simulated_wallet_balances")
    op.drop_table("blockchain_networks")
