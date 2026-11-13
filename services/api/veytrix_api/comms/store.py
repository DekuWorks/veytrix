"""Durable storage for conversations. Messages are append-only; ordering is by `seq`.

`append_message` locks the conversation row, takes the next `seq`, and inserts. Callers
commit once per request. Realtime publishing happens only after that commit.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from veytrix_api.comms import roster
from veytrix_api.comms.envelope import (
    ORIGIN_LABELS,
    Citation,
    ConversationOut,
    MemberOut,
    MessageOut,
)
from veytrix_api.models import (
    AgentPresenceRow,
    ConversationMemberRow,
    ConversationRow,
    ConversationSummaryRow,
    MessageEventRow,
    MessageRow,
)

HUMAN = "HUMAN"
SYSTEM = "SYSTEM"
MAX_CONTENT = 4000
SUMMARY_EVERY = 20


class StoreError(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def create_conversation(
    db: Session,
    *,
    kind: str,
    title: str,
    topic: str,
    agents: list[str],
    created_by: str = "human",
    max_rounds: int = 0,
    max_messages: int = 200,
    agenda: list[str] | None = None,
    moderator: str | None = None,
) -> ConversationRow:
    conv = ConversationRow(
        id=uuid.uuid4(),
        kind=kind,
        title=title[:120],
        topic=topic[:300],
        status="open",
        pinned=False,
        created_by=created_by,
        max_rounds=max_rounds,
        max_messages=max_messages,
        agenda=agenda,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(conv)
    db.flush()
    db.add(
        ConversationMemberRow(
            conversation_id=conv.id,
            member_id=HUMAN,
            member_kind="human",
            role="owner",
            last_read_seq=0,
            joined_at=_now(),
        )
    )
    for code in dict.fromkeys(agents):
        if code not in roster.BY_CODE:
            raise StoreError(f"Unknown desk {code}.")
        db.add(
            ConversationMemberRow(
                conversation_id=conv.id,
                member_id=code,
                member_kind="agent",
                role="moderator" if code == moderator else "participant",
                last_read_seq=0,
                joined_at=_now(),
            )
        )
    db.flush()
    return conv


def get_conversation(db: Session, conversation_id: uuid.UUID, *, lock: bool = False):
    stmt = select(ConversationRow).where(ConversationRow.id == conversation_id)
    if lock:
        stmt = stmt.with_for_update()
    return db.scalars(stmt).first()


def members(db: Session, conversation_id: uuid.UUID) -> list[ConversationMemberRow]:
    rows = list(
        db.scalars(
            select(ConversationMemberRow).where(
                ConversationMemberRow.conversation_id == conversation_id
            )
        )
    )
    order = {code: index for index, code in enumerate(roster.CODES)}
    rows.sort(key=lambda r: (r.member_kind != "human", order.get(r.member_id, 99)))
    return rows


def agent_members(db: Session, conversation_id: uuid.UUID) -> list[str]:
    return [m.member_id for m in members(db, conversation_id) if m.member_kind == "agent"]


def get_or_create_direct(db: Session, code: str) -> ConversationRow:
    if code not in roster.BY_CODE:
        raise StoreError(f"Unknown desk {code}.")
    stmt = (
        select(ConversationRow)
        .join(ConversationMemberRow, ConversationMemberRow.conversation_id == ConversationRow.id)
        .where(
            ConversationRow.kind == "direct",
            ConversationMemberRow.member_id == code,
            ConversationRow.status != "archived",
        )
        .order_by(ConversationRow.created_at.asc())
        .limit(1)
    )
    existing = db.scalars(stmt).first()
    if existing is not None:
        return existing
    desk = roster.desk_for(code)
    return create_conversation(
        db,
        kind="direct",
        title=f"{desk.name} · {desk.role}",
        topic=f"Direct chat with {desk.name}",
        agents=[code],
        max_messages=500,
    )


def message_count(db: Session, conversation_id: uuid.UUID) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(MessageRow)
            .where(MessageRow.conversation_id == conversation_id)
        )
        or 0
    )


def last_seq(db: Session, conversation_id: uuid.UUID) -> int:
    return (
        db.scalar(
            select(func.max(MessageRow.seq)).where(MessageRow.conversation_id == conversation_id)
        )
        or 0
    )


def append_message(
    db: Session,
    conv: ConversationRow,
    *,
    sender_id: str,
    sender_kind: str,
    content: str,
    kind: str,
    origin: str,
    correlation_id: str,
    recipients: list[str] | None = None,
    thread_id: uuid.UUID | None = None,
    citations: list[Citation] | None = None,
    meta: dict[str, object] | None = None,
    task_id: str | None = None,
    decision_id: str | None = None,
    tool_call_id: str | None = None,
    client_message_id: str | None = None,
    visibility: str = "conversation",
) -> MessageRow:
    if (sender_kind == "human") != (origin == "human"):
        raise StoreError("Only a human message has origin human.")
    if sender_kind == "agent" and sender_id not in roster.BY_CODE:
        raise StoreError("Unknown agent sender.")
    text = content.strip()
    if not text:
        raise StoreError("Empty message.")
    if len(text) > MAX_CONTENT:
        text = text[: MAX_CONTENT - 1].rstrip() + "…"
    # Lock the row so two writers cannot take the same seq.
    locked = get_conversation(db, conv.id, lock=True)
    if locked is None:
        raise StoreError("Conversation not found.")
    seq = last_seq(db, conv.id) + 1
    row = MessageRow(
        id=uuid.uuid4(),
        conversation_id=conv.id,
        seq=seq,
        thread_id=thread_id,
        sender_id=sender_id,
        sender_kind=sender_kind,
        recipient_ids=list(recipients or []),
        kind=kind,
        origin=origin,
        correlation_id=correlation_id[:64],
        task_id=task_id,
        decision_id=decision_id,
        tool_call_id=tool_call_id,
        client_message_id=client_message_id,
        content=text,
        status="delivered",
        visibility=visibility,
        citations=[c.model_dump() for c in (citations or [])],
        meta=dict(meta or {}),
        created_at=_now(),
    )
    db.add(row)
    conv.updated_at = _now()
    db.flush()
    return row


def record_event(
    db: Session,
    conversation_id: uuid.UUID,
    event_type: str,
    *,
    actor: str,
    correlation_id: str,
    message_id: uuid.UUID | None = None,
    payload: dict[str, object] | None = None,
) -> None:
    db.add(
        MessageEventRow(
            id=uuid.uuid4(),
            conversation_id=conversation_id,
            message_id=message_id,
            event_type=event_type[:32],
            actor=actor[:32],
            correlation_id=correlation_id[:64],
            payload=dict(payload or {}),
            created_at=_now(),
        )
    )
    db.flush()


def find_by_client_id(db: Session, conversation_id: uuid.UUID, client_id: str) -> MessageRow | None:
    return db.scalars(
        select(MessageRow).where(
            MessageRow.conversation_id == conversation_id,
            MessageRow.client_message_id == client_id,
        )
    ).first()


def replies_after(db: Session, conversation_id: uuid.UUID, seq: int) -> list[MessageRow]:
    return list(
        db.scalars(
            select(MessageRow)
            .where(MessageRow.conversation_id == conversation_id, MessageRow.seq > seq)
            .order_by(MessageRow.seq.asc())
        )
    )


def list_messages(
    db: Session, conversation_id: uuid.UUID, *, after_seq: int = 0, limit: int = 50
) -> tuple[list[MessageRow], bool]:
    rows = list(
        db.scalars(
            select(MessageRow)
            .where(MessageRow.conversation_id == conversation_id, MessageRow.seq > after_seq)
            .order_by(MessageRow.seq.asc())
            .limit(limit + 1)
        )
    )
    return rows[:limit], len(rows) > limit


def recent(db: Session, conversation_id: uuid.UUID, limit: int = 12) -> list[MessageRow]:
    """Bounded context, newest first."""

    return list(
        db.scalars(
            select(MessageRow)
            .where(MessageRow.conversation_id == conversation_id)
            .order_by(MessageRow.seq.desc())
            .limit(limit)
        )
    )


def latest_objection(db: Session, code: str) -> tuple[MessageRow, str] | None:
    row = db.scalars(
        select(MessageRow)
        .where(MessageRow.sender_id == code, MessageRow.kind == "objection")
        .order_by(MessageRow.created_at.desc())
        .limit(1)
    ).first()
    if row is None:
        return None
    conv = db.get(ConversationRow, row.conversation_id)
    return row, conv.title if conv else "a discussion"


def feed(db: Session, *, limit: int = 40, after: datetime | None = None) -> list[MessageRow]:
    """Latest agent and system messages across all conversations, oldest first.

    Simulated peer chatter and the old “nothing is running” / disabled placeholders
    stay in the transcript. They are not the live floor.
    """

    stmt = select(MessageRow).where(
        MessageRow.sender_kind != "human",
        MessageRow.visibility == "conversation",
        MessageRow.origin != "simulated",
        ~MessageRow.content.ilike("%you said%"),
        ~MessageRow.content.ilike("%Nothing is running on this desk%"),
        ~MessageRow.content.ilike("%Registry status is disabled%"),
    )
    if after is not None:
        stmt = stmt.where(MessageRow.created_at > after)
    rows = list(db.scalars(stmt.order_by(MessageRow.created_at.desc()).limit(limit)))
    rows.reverse()
    return rows


def mark_read(db: Session, conversation_id: uuid.UUID, seq: int) -> None:
    member = db.get(ConversationMemberRow, (conversation_id, HUMAN))
    if member is not None and seq > member.last_read_seq:
        member.last_read_seq = min(seq, last_seq(db, conversation_id))
        db.flush()


def set_presence(db: Session, code: str, state: str, conversation_id: uuid.UUID | None) -> None:
    row = db.get(AgentPresenceRow, code)
    if row is None:
        db.add(
            AgentPresenceRow(
                agent_code=code, state=state, conversation_id=conversation_id, updated_at=_now()
            )
        )
    else:
        row.state = state
        row.conversation_id = conversation_id
        row.updated_at = _now()
    db.flush()


def presence_map(db: Session) -> dict[str, str]:
    now = _now()
    out = {code: "idle" for code in roster.CODES}
    for row in db.scalars(select(AgentPresenceRow)):
        if row.agent_code in out and (now - _aware(row.updated_at)).total_seconds() < 600:
            out[row.agent_code] = row.state
    return out


def add_summary(
    db: Session, conversation_id: uuid.UUID, upto_seq: int, text: str, origin: str
) -> None:
    db.add(
        ConversationSummaryRow(
            id=uuid.uuid4(),
            conversation_id=conversation_id,
            upto_seq=upto_seq,
            summary=text[:4000],
            origin=origin,
            created_at=_now(),
        )
    )
    db.flush()


def maybe_summarise(db: Session, conv: ConversationRow, correlation_id: str) -> None:
    """Every SUMMARY_EVERY messages store a plain count-and-questions summary for search."""

    total = message_count(db, conv.id)
    if total == 0 or total % SUMMARY_EVERY != 0:
        return
    asked = list(
        db.scalars(
            select(MessageRow.content)
            .where(MessageRow.conversation_id == conv.id, MessageRow.sender_kind == "human")
            .order_by(MessageRow.seq.desc())
            .limit(5)
        )
    )
    text = f"{total} messages. Recent questions: " + " | ".join(a[:80] for a in reversed(asked))
    add_summary(db, conv.id, last_seq(db, conv.id), text, "tool_verified")


# --- serialisation -----------------------------------------------------------------------


def message_out(row: MessageRow) -> MessageOut:
    return MessageOut(
        message_id=row.id,
        conversation_id=row.conversation_id,
        seq=row.seq,
        thread_id=row.thread_id,
        sender_id=row.sender_id,
        sender_name=(
            roster.name_of(row.sender_id)
            if row.sender_kind == "agent"
            else ("You" if row.sender_kind == "human" else row.sender_id.title())
        ),
        sender_kind=row.sender_kind,  # type: ignore[arg-type]
        recipient_ids=list(row.recipient_ids or []),
        kind=row.kind,  # type: ignore[arg-type]
        origin=row.origin,  # type: ignore[arg-type]
        origin_label=ORIGIN_LABELS.get(row.origin, row.origin),
        timestamp=_aware(row.created_at),
        correlation_id=row.correlation_id,
        task_id=row.task_id,
        decision_id=row.decision_id,
        tool_call_id=row.tool_call_id,
        content=row.content,
        status=row.status,  # type: ignore[arg-type]
        visibility=row.visibility,  # type: ignore[arg-type]
        citations=[Citation(**c) for c in (row.citations or [])],
        meta=dict(row.meta or {}),
    )


def conversation_out(db: Session, conv: ConversationRow) -> ConversationOut:
    mem = members(db, conv.id)
    human = next((m for m in mem if m.member_id == HUMAN), None)
    total = message_count(db, conv.id)
    newest = last_seq(db, conv.id)
    last = db.scalars(
        select(MessageRow)
        .where(MessageRow.conversation_id == conv.id)
        .order_by(MessageRow.seq.desc())
        .limit(1)
    ).first()
    read = human.last_read_seq if human else 0
    return ConversationOut(
        conversation_id=conv.id,
        kind=conv.kind,  # type: ignore[arg-type]
        title=conv.title,
        topic=conv.topic,
        status=conv.status,  # type: ignore[arg-type]
        pinned=conv.pinned,
        created_by=conv.created_by,  # type: ignore[arg-type]
        owner_id=conv.owner_id,
        max_rounds=conv.max_rounds,
        max_messages=conv.max_messages,
        created_at=_aware(conv.created_at),
        updated_at=_aware(conv.updated_at),
        closed_at=_aware(conv.closed_at) if conv.closed_at else None,
        message_count=total,
        unread=max(0, newest - read),
        members=[
            MemberOut(
                member_id=m.member_id,
                member_name="You" if m.member_kind == "human" else roster.name_of(m.member_id),
                member_kind=m.member_kind,  # type: ignore[arg-type]
                role=m.role,
                last_read_seq=m.last_read_seq,
            )
            for m in mem
        ],
        agenda=list(conv.agenda) if conv.agenda else None,
        last_message=message_out(last) if last is not None else None,
    )


def list_conversations(
    db: Session, *, include_archived: bool = False, query: str | None = None, limit: int = 60
) -> list[ConversationRow]:
    stmt = select(ConversationRow)
    if not include_archived:
        stmt = stmt.where(ConversationRow.status != "archived")
    if query:
        escaped = query.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like = f"%{escaped}%"
        in_messages = select(MessageRow.conversation_id).where(
            func.lower(MessageRow.content).like(like, escape="\\")
        )
        in_summaries = select(ConversationSummaryRow.conversation_id).where(
            func.lower(ConversationSummaryRow.summary).like(like, escape="\\")
        )
        stmt = stmt.where(
            or_(
                func.lower(ConversationRow.title).like(like, escape="\\"),
                func.lower(ConversationRow.topic).like(like, escape="\\"),
                ConversationRow.id.in_(in_messages),
                ConversationRow.id.in_(in_summaries),
            )
        )
    stmt = stmt.order_by(ConversationRow.pinned.desc(), ConversationRow.updated_at.desc()).limit(
        limit
    )
    return list(db.scalars(stmt))
