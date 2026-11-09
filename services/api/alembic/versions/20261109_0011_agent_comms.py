"""Agent communication store in schema private.

Six tables: conversations, conversation_members, messages, message_events,
agent_presence, conversation_summaries. Messages and message events are
append-only. None of these tables holds an order, a key, or a broker field.

Rollback: `alembic downgrade 0010_futures_desk` drops the six tables. No other
table is touched, so the registry and the audit log are unaffected.

Revision ID: 0011_agent_comms
Revises: 0010_futures_desk
Create Date: 2026-11-09
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_agent_comms"
down_revision: str | None = "0010_futures_desk"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CODES = (
    "'SUPERVISOR-01', 'DAY-01', 'STOCK-01', 'CRYPTO-01', 'DEFI-01', "
    "'ETF-01', 'FUTURES-01', 'RESEARCH-01', 'RISK-01', 'TREASURY-01'"
)
TABLES = (
    "conversations",
    "conversation_members",
    "messages",
    "message_events",
    "agent_presence",
    "conversation_summaries",
)


def _now() -> sa.TextClause:
    return sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("topic", sa.String(length=300), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by", sa.String(length=16), nullable=False),
        sa.Column("max_rounds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_messages", sa.Integer(), nullable=False, server_default="200"),
        sa.Column("owner_id", sa.String(length=32), nullable=True),
        sa.Column("agenda", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_now(), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "kind IN ('direct', 'group', 'discussion', 'boardroom')", name="ck_conversations_kind"
        ),
        sa.CheckConstraint(
            "status IN ('open', 'paused', 'closed', 'archived')", name="ck_conversations_status"
        ),
        sa.CheckConstraint("created_by IN ('human', 'system')", name="ck_conversations_creator"),
        sa.CheckConstraint("max_rounds BETWEEN 0 AND 5", name="ck_conversations_rounds"),
        sa.CheckConstraint("max_messages BETWEEN 1 AND 500", name="ck_conversations_budget"),
        sa.CheckConstraint("char_length(title) BETWEEN 1 AND 120", name="ck_conversations_title"),
        schema="private",
    )
    op.create_index("ix_conversations_updated", "conversations", ["updated_at"], schema="private")

    op.create_table(
        "conversation_members",
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("private.conversations.id", name="fk_members_conversation"),
            nullable=False,
        ),
        sa.Column("member_id", sa.String(length=32), nullable=False),
        sa.Column("member_kind", sa.String(length=8), nullable=False),
        sa.Column("role", sa.String(length=12), nullable=False),
        sa.Column("last_read_seq", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=_now(), nullable=False),
        sa.PrimaryKeyConstraint("conversation_id", "member_id", name="pk_conversation_members"),
        sa.CheckConstraint("member_kind IN ('human', 'agent')", name="ck_members_kind"),
        sa.CheckConstraint(
            "role IN ('participant', 'moderator', 'owner', 'observer')", name="ck_members_role"
        ),
        sa.CheckConstraint(
            f"(member_kind = 'human' AND member_id = 'HUMAN') "
            f"OR (member_kind = 'agent' AND member_id IN ({CODES}))",
            name="ck_members_identity",
        ),
        schema="private",
    )

    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("private.conversations.id", name="fk_messages_conversation"),
            nullable=False,
        ),
        sa.Column("seq", sa.BigInteger(), nullable=False),
        sa.Column("thread_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sender_id", sa.String(length=32), nullable=False),
        sa.Column("sender_kind", sa.String(length=8), nullable=False),
        sa.Column("recipient_ids", postgresql.JSONB(), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("origin", sa.String(length=16), nullable=False),
        sa.Column("correlation_id", sa.String(length=64), nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=True),
        sa.Column("decision_id", sa.String(length=64), nullable=True),
        sa.Column("tool_call_id", sa.String(length=64), nullable=True),
        sa.Column("client_message_id", sa.String(length=64), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("visibility", sa.String(length=16), nullable=False),
        sa.Column("citations", postgresql.JSONB(), nullable=False),
        sa.Column("meta", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_now(), nullable=False),
        sa.UniqueConstraint("conversation_id", "seq", name="uq_messages_conversation_seq"),
        sa.CheckConstraint(
            "sender_kind IN ('human', 'agent', 'system', 'tool')", name="ck_messages_sender_kind"
        ),
        sa.CheckConstraint(
            "origin IN ('human', 'scripted', 'model_generated', 'tool_verified', 'simulated')",
            name="ck_messages_origin",
        ),
        sa.CheckConstraint(
            "(sender_kind = 'human' AND origin = 'human') "
            "OR (sender_kind <> 'human' AND origin <> 'human')",
            name="ck_messages_origin_matches_sender",
        ),
        sa.CheckConstraint(
            "sender_kind <> 'agent' OR sender_id IN (" + CODES + ")",
            name="ck_messages_agent_sender",
        ),
        sa.CheckConstraint(
            "status IN ('delivered', 'failed', 'cancelled')", name="ck_messages_status"
        ),
        sa.CheckConstraint(
            "visibility IN ('conversation', 'private')", name="ck_messages_visibility"
        ),
        sa.CheckConstraint("char_length(content) BETWEEN 1 AND 4000", name="ck_messages_content"),
        sa.CheckConstraint("seq >= 1", name="ck_messages_seq"),
        schema="private",
    )
    op.create_index(
        "uq_messages_client_message",
        "messages",
        ["conversation_id", "client_message_id"],
        unique=True,
        schema="private",
        postgresql_where=sa.text("client_message_id IS NOT NULL"),
    )
    op.create_index("ix_messages_created", "messages", ["created_at"], schema="private")
    op.create_index("ix_messages_correlation", "messages", ["correlation_id"], schema="private")

    op.create_table(
        "message_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("private.conversations.id", name="fk_events_conversation"),
            nullable=False,
        ),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("actor", sa.String(length=32), nullable=False),
        sa.Column("correlation_id", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_now(), nullable=False),
        sa.CheckConstraint("char_length(event_type) BETWEEN 1 AND 32", name="ck_events_type"),
        schema="private",
    )
    op.create_index(
        "ix_message_events_conversation",
        "message_events",
        ["conversation_id", "created_at"],
        schema="private",
    )

    op.create_table(
        "agent_presence",
        sa.Column("agent_code", sa.String(length=32), primary_key=True),
        sa.Column("state", sa.String(length=24), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_now(), nullable=False),
        sa.CheckConstraint(f"agent_code IN ({CODES})", name="ck_presence_agent"),
        sa.CheckConstraint(
            "state IN ('idle', 'listening', 'composing', 'speaking', 'meeting')",
            name="ck_presence_state",
        ),
        schema="private",
    )

    op.create_table(
        "conversation_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("private.conversations.id", name="fk_summaries_conversation"),
            nullable=False,
        ),
        sa.Column("upto_seq", sa.BigInteger(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("origin", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_now(), nullable=False),
        sa.CheckConstraint(
            "origin IN ('scripted', 'model_generated', 'tool_verified', 'simulated')",
            name="ck_summaries_origin",
        ),
        sa.CheckConstraint("char_length(summary) BETWEEN 1 AND 4000", name="ck_summaries_body"),
        schema="private",
    )

    for table in ("messages", "message_events"):
        for verb, level in (("update", "ROW"), ("delete", "ROW"), ("truncate", "STATEMENT")):
            op.execute(
                sa.text(
                    f"""
                    CREATE TRIGGER {table}_no_{verb}
                    BEFORE {verb.upper()} ON private.{table}
                    FOR EACH {level}
                    EXECUTE FUNCTION private.reject_mutation()
                    """
                )
            )

    for table in TABLES:
        op.execute(sa.text(f"ALTER TABLE private.{table} ENABLE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"ALTER TABLE private.{table} FORCE ROW LEVEL SECURITY"))
        op.execute(
            sa.text(
                f"""
                CREATE POLICY {table}_local_role ON private.{table}
                FOR ALL
                TO veytrix
                USING (true)
                WITH CHECK (true)
                """
            )
        )


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(sa.text(f"DROP TABLE IF EXISTS private.{table} CASCADE"))
