"""Conversations between the user and the ten desks, and between desks.

Nothing here places an order. No route here calls a broker, MAC-01, or the swap CLI, and the
module imports none of them. A reply is composed from read-only local records (see
`veytrix_api.comms.replies`). Messages are stored before they are announced.
"""

from __future__ import annotations

import functools
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from veytrix_api.comms import (
    delegate,
    discussion,
    replies,
    roster,
    safety,
    store,
    stream_chat,
    work,
)
from veytrix_api.comms.envelope import (
    Citation,
    ConversationEnvelope,
    ConversationListResponse,
    CreateConversation,
    FeedResponse,
    FlagsResponse,
    MessageListResponse,
    Moderate,
    PatchConversation,
    PresenceOut,
    PresenceResponse,
    ReadMark,
    RosterEntry,
    RosterResponse,
    SendMessage,
    SendResult,
    StartDiscussion,
    TaskListResponse,
    TaskOut,
    TriggerBody,
)
from veytrix_api.comms.realtime import Notifier
from veytrix_api.db import get_db
from veytrix_api.logging_config import correlation_id_var
from veytrix_api.models import AgentPresenceRow, ConversationRow, MessageRow, ResearchTaskRow
from veytrix_api.ratelimit import ProcessLocalRateLimiter
from veytrix_api.schemas import DENIED_TOOLS
from veytrix_api.settings import Settings

router = APIRouter(prefix="/comms", tags=["comms"])
STORE_DOWN = "Conversation store is unavailable. Run alembic upgrade head on the local database."
FLAG_NOTE = (
    "Language is English (en). No language model is configured. Replies are verified from "
    "local records and labelled. live_execution is fixed off and cannot be enabled by a "
    "setting or a message."
)
ALL_HANDS = "All desks"
AUTO_COOLDOWN = timedelta(minutes=15)
AUTO_TOPICS = {
    "reconcile": "Review how the local ledger compares with broker records",
    "risk_check": "Review the paper risk limits and the kill switch",
    "position_size": "Review the stored paper size rows",
    "sma_crossover": "Review the stored MAC-01 SMA 20/50 signals",
    "treasury_split": "Review the local month projection inputs",
}


def store_errors(fn):
    """Turn a database failure into a clear 503 and a rollback. Other errors pass through."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        db = kwargs.get("db")
        try:
            return fn(*args, **kwargs)
        except store.StoreError as exc:
            if db is not None:
                db.rollback()
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except SQLAlchemyError as exc:
            if db is not None:
                db.rollback()
            raise HTTPException(status_code=503, detail=STORE_DOWN) from exc

    return wrapper


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _flags(settings: Settings) -> dict[str, bool]:
    return {
        "agent_chat": settings.flag_agent_chat,
        "group_chat": settings.flag_group_chat,
        "autonomous_discussions": settings.flag_autonomous_discussions,
        "voice_chat": settings.flag_voice_chat,
        "live_execution": safety.LIVE_EXECUTION_ENABLED,
    }


def _require(request: Request, flag: str) -> None:
    if not _flags(_settings(request))[flag]:
        raise HTTPException(status_code=403, detail=f"Feature flag {flag} is off.")


def _notifier(request: Request) -> Notifier:
    existing = getattr(request.app.state, "comms_notifier", None)
    if existing is not None:
        return existing
    settings = _settings(request)
    notifier = Notifier(settings.realtime_url, settings.realtime_server_key.get_secret_value())
    request.app.state.comms_notifier = notifier
    return notifier


def _throttle(request: Request) -> None:
    limiter = getattr(request.app.state, "comms_limiter", None)
    if limiter is None:
        per_minute = _settings(request).comms_messages_per_minute
        limiter = ProcessLocalRateLimiter(
            per_minute, burst=min(max(10, per_minute // 6), per_minute)
        )
        request.app.state.comms_limiter = limiter
    client = request.client.host if request.client else "unknown"
    allowed, _ = limiter.check(f"comms:{client}")
    if not allowed:
        raise HTTPException(status_code=429, detail="Too many messages. Slow down.")


def _correlation() -> str:
    return correlation_id_var.get() or str(uuid.uuid4())


def _conversation(db: Session, conversation_id: uuid.UUID) -> ConversationRow:
    conv = store.get_conversation(db, conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return conv


def _announce(request: Request, db: Session, rows: list[MessageRow], correlation_id: str) -> str:
    """Publish a doorbell for each stored message. Runs only after the commit."""

    notifier = _notifier(request)
    if not notifier.configured:
        return "not_configured"
    seen: set[str] = set()
    for row in rows:
        result = notifier.publish(
            {
                "conversation_id": row.conversation_id,
                "seq": row.seq,
                "message_id": row.id,
                "sender_id": row.sender_id,
                "origin": row.origin,
            }
        )
        seen.add(result)
        try:
            store.record_event(
                db,
                row.conversation_id,
                f"realtime_{result}",
                actor="SYSTEM",
                correlation_id=correlation_id,
                message_id=row.id,
                payload={"seq": row.seq},
            )
            db.commit()
        except SQLAlchemyError:
            db.rollback()
    return "failed" if "failed" in seen else "published"


@router.get("/flags", response_model=FlagsResponse)
def flags(request: Request) -> FlagsResponse:
    settings = _settings(request)
    return FlagsResponse(
        flags=_flags(settings),
        realtime=_notifier(request).status(),
        note=FLAG_NOTE,  # type: ignore[arg-type]
    )


@router.get("/roster", response_model=RosterResponse)
def roster_route(db: Session = Depends(get_db)) -> RosterResponse:
    try:
        presence = store.presence_map(db)
    except SQLAlchemyError:
        db.rollback()
        presence = {code: "idle" for code in roster.CODES}
    return RosterResponse(
        desks=[
            RosterEntry(
                code=d.code,
                registry_id=d.registry_id,
                name=d.name,
                role=d.role,
                desk=d.desk,
                summary=d.summary,
                tools_denied=len(DENIED_TOOLS),
                presence=presence.get(d.code, "idle"),
            )
            for d in roster.DESKS
        ]
    )


@router.get("/conversations", response_model=ConversationListResponse)
@store_errors
def list_conversations(
    archived: bool = False,
    q: str | None = Query(default=None, max_length=80),
    db: Session = Depends(get_db),
) -> ConversationListResponse:
    rows = store.list_conversations(db, include_archived=archived, query=q)
    return ConversationListResponse(conversations=[store.conversation_out(db, r) for r in rows])


@router.post("/conversations", response_model=ConversationEnvelope)
@store_errors
def create_conversation(
    body: CreateConversation, request: Request, db: Session = Depends(get_db)
) -> ConversationEnvelope:
    _throttle(request)
    if body.kind == "direct":
        _require(request, "agent_chat")
        if body.agent_code not in roster.BY_CODE:
            raise HTTPException(status_code=422, detail="agent_code must be one of the ten desks.")
        conv = store.get_or_create_direct(db, body.agent_code)
    elif body.kind == "group":
        _require(request, "group_chat")
        if body.participants:
            bad = [c for c in body.participants if c not in roster.BY_CODE]
            if bad:
                raise HTTPException(status_code=422, detail="Unknown desk in participants.")
        codes = list(dict.fromkeys(body.participants or roster.CODES))
        if len(codes) < 2:
            raise HTTPException(status_code=422, detail="A group needs at least two desks.")
        all_hands = set(codes) == set(roster.CODES) and not body.title
        if all_hands:
            existing = db.scalars(
                select(ConversationRow)
                .where(
                    ConversationRow.kind == "group",
                    ConversationRow.title == ALL_HANDS,
                    ConversationRow.status != "archived",
                )
                .limit(1)
            ).first()
            if existing is not None:
                return ConversationEnvelope(conversation=store.conversation_out(db, existing))
        title = (
            ALL_HANDS
            if all_hands
            else (body.title or "Group · " + ", ".join(roster.name_of(c) for c in codes[:4]))
        )
        conv = store.create_conversation(
            db,
            kind="group",
            title=title,
            topic="Group chat. Mention a desk with @Name or @all.",
            agents=codes,
            moderator=roster.SUPERVISOR if roster.SUPERVISOR in codes else None,
            max_messages=500,
        )
    else:
        raise HTTPException(
            status_code=422, detail="Start a discussion or boardroom with POST /comms/discussions."
        )
    out = store.conversation_out(db, conv)
    db.commit()
    return ConversationEnvelope(conversation=out)


@router.get("/conversations/{conversation_id}", response_model=ConversationEnvelope)
@store_errors
def get_conversation(
    conversation_id: uuid.UUID, db: Session = Depends(get_db)
) -> ConversationEnvelope:
    return ConversationEnvelope(
        conversation=store.conversation_out(db, _conversation(db, conversation_id))
    )


@router.patch("/conversations/{conversation_id}", response_model=ConversationEnvelope)
@store_errors
def patch_conversation(
    conversation_id: uuid.UUID, body: PatchConversation, db: Session = Depends(get_db)
) -> ConversationEnvelope:
    conv = _conversation(db, conversation_id)
    if body.pinned is not None:
        conv.pinned = body.pinned
    if body.title is not None:
        conv.title = safety.clean(body.title, 120)
    if body.archived is True:
        conv.status = "archived"
    elif body.archived is False and conv.status == "archived":
        conv.status = "closed" if conv.closed_at else "open"
    conv.updated_at = datetime.now(UTC)
    out = store.conversation_out(db, conv)
    db.commit()
    return ConversationEnvelope(conversation=out)


@router.get("/conversations/{conversation_id}/messages", response_model=MessageListResponse)
@store_errors
def list_messages(
    conversation_id: uuid.UUID,
    after_seq: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> MessageListResponse:
    _conversation(db, conversation_id)
    rows, more = store.list_messages(db, conversation_id, after_seq=after_seq, limit=limit)
    return MessageListResponse(
        conversation_id=conversation_id,
        messages=[store.message_out(r) for r in rows],
        has_more=more,
        next_after_seq=rows[-1].seq if rows else after_seq,
    )


@router.post("/conversations/{conversation_id}/read", response_model=ConversationEnvelope)
@store_errors
def mark_read(
    conversation_id: uuid.UUID, body: ReadMark, db: Session = Depends(get_db)
) -> ConversationEnvelope:
    conv = _conversation(db, conversation_id)
    store.mark_read(db, conversation_id, body.seq)
    out = store.conversation_out(db, conv)
    db.commit()
    return ConversationEnvelope(conversation=out)


def _responders(db: Session, conv: ConversationRow, text: str) -> list[str]:
    members = store.agent_members(db, conv.id)
    if conv.kind == "direct":
        return members[:1]
    named, everyone = roster.mentions(text)
    if everyone:
        return members
    picked = [c for c in named if c in members]
    if picked:
        return picked
    related = [c for c in roster.relevant_desks(text, limit=3) if c in members]
    if related:
        return related
    if roster.SUPERVISOR in members:
        return [roster.SUPERVISOR]
    return members[:1]


@router.post("/conversations/{conversation_id}/messages", response_model=SendResult)
@store_errors
def send_message(
    conversation_id: uuid.UUID,
    body: SendMessage,
    request: Request,
    db: Session = Depends(get_db),
) -> SendResult:
    _throttle(request)
    conv = _conversation(db, conversation_id)
    _require(request, "agent_chat" if conv.kind == "direct" else "group_chat")
    if conv.status == "archived":
        raise HTTPException(status_code=409, detail="Conversation is archived.")
    correlation = _correlation()

    if body.client_message_id:
        prior = store.find_by_client_id(db, conv.id, body.client_message_id)
        if prior is not None:
            again = [prior, *store.replies_after(db, conv.id, prior.seq)]
            return SendResult(
                conversation=store.conversation_out(db, conv),
                messages=[store.message_out(r) for r in again],
                duplicate=True,
            )
    if body.thread_id is not None:
        parent = db.get(MessageRow, body.thread_id)
        if parent is None or parent.conversation_id != conv.id:
            raise HTTPException(status_code=422, detail="thread_id is not in this conversation.")

    responders = _responders(db, conv, body.content)
    human = store.append_message(
        db,
        conv,
        sender_id=store.HUMAN,
        sender_kind="human",
        content=body.content,
        kind="question" if body.content.rstrip().endswith("?") else "chat",
        origin="human",
        correlation_id=correlation,
        recipients=responders,
        thread_id=body.thread_id,
        client_message_id=body.client_message_id,
    )
    new_rows: list[MessageRow] = [human]
    errors: list[str] = []
    held: str | None = None
    store.record_event(
        db,
        conv.id,
        "delivered",
        actor=store.HUMAN,
        correlation_id=correlation,
        message_id=human.id,
        payload={"seq": human.seq},
    )

    if conv.status == "paused":
        held = "paused"
        store.record_event(
            db,
            conv.id,
            "held_paused",
            actor="SYSTEM",
            correlation_id=correlation,
            message_id=human.id,
            payload={},
        )
    else:
        thread = body.thread_id or human.id
        delegated = False
        if roster.SUPERVISOR in responders and delegate.matches(body.content):
            parsed = delegate.parse(body.content)
            if parsed is not None:
                new_rows.extend(delegate.assign(db, conv, body.content, correlation, thread))
                delegated = True
        for code in responders:
            if delegated and code == roster.SUPERVISOR:
                continue
            if store.message_count(db, conv.id) >= conv.max_messages:
                store.record_event(
                    db,
                    conv.id,
                    "budget_exhausted",
                    actor="SYSTEM",
                    correlation_id=correlation,
                    payload={"before": code},
                )
                errors.append("budget_exhausted")
                break
            try:
                reply = replies.compose_reply(
                    db,
                    code,
                    body.content,
                    history=store.recent(db, conv.id, 12),
                    level=body.level,
                    brief=len(responders) > 1,
                )
                row = store.append_message(
                    db,
                    conv,
                    sender_id=code,
                    sender_kind="agent",
                    content=reply.content,
                    kind=reply.kind,
                    origin=reply.origin,
                    correlation_id=correlation,
                    recipients=[store.HUMAN],
                    thread_id=thread,
                    citations=reply.citations,
                    meta=reply.meta,
                )
            except SQLAlchemyError:
                raise
            except Exception:
                db.rollback()
                errors.append(f"reply_failed:{code}")
                continue
            new_rows.append(row)
            store.set_presence(db, code, "speaking", conv.id)
            store.record_event(
                db,
                conv.id,
                "delivered",
                actor=code,
                correlation_id=correlation,
                message_id=row.id,
                payload={"seq": row.seq, "origin": row.origin},
            )
    store.mark_read(db, conv.id, store.last_seq(db, conv.id))
    store.maybe_summarise(db, conv, correlation)
    out = store.conversation_out(db, conv)
    messages = [store.message_out(r) for r in new_rows]
    db.commit()
    realtime = _announce(request, db, new_rows, correlation)
    return SendResult(
        conversation=out,
        messages=messages,
        held=held,
        errors=errors,
        realtime=realtime,  # type: ignore[arg-type]
    )


@router.post("/conversations/{conversation_id}/messages/stream")
@store_errors
def stream_message(
    conversation_id: uuid.UUID,
    body: SendMessage,
    request: Request,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Stream one desk reply. Delegation only queues tasks; the worker answers later."""

    _throttle(request)
    conv = _conversation(db, conversation_id)
    _require(request, "agent_chat" if conv.kind == "direct" else "group_chat")
    if conv.status == "archived":
        raise HTTPException(status_code=409, detail="Conversation is archived.")
    if body.thread_id is not None:
        parent = db.get(MessageRow, body.thread_id)
        if parent is None or parent.conversation_id != conv.id:
            raise HTTPException(status_code=422, detail="thread_id is not in this conversation.")
    responders = _responders(db, conv, body.content)
    correlation = _correlation()

    def events():
        try:
            yield from stream_chat.iter_chat_events(db, conv, body, correlation, responders)
        except store.StoreError as exc:
            db.rollback()
            yield stream_chat.sse("error", {"detail": str(exc)})
        except SQLAlchemyError:
            db.rollback()
            yield stream_chat.sse("error", {"detail": STORE_DOWN})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/tasks", response_model=TaskListResponse)
@store_errors
def list_tasks(
    conversation_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
) -> TaskListResponse:
    stmt = select(ResearchTaskRow).order_by(ResearchTaskRow.created_at.desc()).limit(50)
    if conversation_id is not None:
        stmt = stmt.where(ResearchTaskRow.conversation_id == conversation_id)
    rows = list(db.scalars(stmt))
    return TaskListResponse(
        tasks=[
            TaskOut(
                id=row.id,
                assignee_code=row.assignee_code,
                subject=row.subject,
                status=row.status,  # type: ignore[arg-type]
                kind=row.kind,  # type: ignore[arg-type]
                evidence_message_id=row.evidence_message_id,
                blocked_reason=row.blocked_reason,
                attempt_count=row.attempt_count,
            )
            for row in rows
        ]
    )


@router.get("/presence", response_model=PresenceResponse)
@store_errors
def worker_presence(db: Session = Depends(get_db)) -> PresenceResponse:
    """Online only when a worker heartbeat is fresh. A chat state is not a heartbeat."""

    from veytrix_api.worker import fresh

    rows = {row.agent_code: row for row in db.scalars(select(AgentPresenceRow))}
    agents: list[PresenceOut] = []
    for code in roster.CODES:
        row = rows.get(code)
        is_fresh = bool(row and fresh(row.heartbeat_at, row.worker_id))
        lifecycle = row.lifecycle if row is not None and is_fresh else "offline"
        agents.append(
            PresenceOut(
                agent_code=code,
                lifecycle=lifecycle,  # type: ignore[arg-type]
                heartbeat_fresh=is_fresh,
                worker_id=row.worker_id if row is not None and is_fresh else None,
                task_id=row.task_id if row is not None and is_fresh else None,
            )
        )
    return PresenceResponse(agents=agents)


@router.post("/discussions", response_model=SendResult)
@store_errors
def start_discussion(
    body: StartDiscussion, request: Request, db: Session = Depends(get_db)
) -> SendResult:
    _throttle(request)
    _require(request, "group_chat")
    correlation = _correlation()
    if body.participants:
        bad = [c for c in body.participants if c not in roster.BY_CODE]
        if bad:
            raise HTTPException(status_code=422, detail="Unknown desk in participants.")
    return _run(
        request,
        db,
        body.topic,
        body.participants,
        body.rounds,
        body.kind,
        body.agenda,
        "human",
        correlation,
    )


def _run(
    request: Request,
    db: Session,
    topic: str,
    requested: list[str] | None,
    rounds: int,
    kind: str,
    agenda: list[str] | None,
    created_by: str,
    correlation: str,
) -> SendResult:
    task_id = f"task-{uuid.uuid4().hex[:12]}"
    if kind == "boardroom":
        items = [safety.clean(a, 120) for a in (agenda or discussion.DEFAULT_AGENDA) if a.strip()]
        items = items[:3] or list(discussion.DEFAULT_AGENDA)
        speakers = list(roster.CODES)
        conv = store.create_conversation(
            db,
            kind="boardroom",
            title="Boardroom session · " + datetime.now(UTC).strftime("%d %b %Y"),
            topic=safety.clean(topic, 300),
            agents=speakers,
            created_by=created_by,
            max_rounds=1,
            max_messages=60,
            agenda=items,
            moderator=roster.SUPERVISOR,
        )
    else:
        speakers = discussion.pick_participants(topic, requested)
        conv = store.create_conversation(
            db,
            kind="discussion",
            title="Discussion · " + safety.clean(topic, 80),
            topic=safety.clean(topic, 300),
            agents=[roster.SUPERVISOR, *speakers],
            created_by=created_by,
            max_rounds=rounds,
            max_messages=40,
            moderator=roster.SUPERVISOR,
        )
    rows: list[MessageRow] = []
    if created_by == "human":
        rows.append(
            store.append_message(
                db,
                conv,
                sender_id=store.HUMAN,
                sender_kind="human",
                content=topic,
                kind="chat",
                origin="human",
                correlation_id=correlation,
                recipients=[roster.SUPERVISOR],
                task_id=task_id,
            )
        )
    for code in speakers:
        store.set_presence(db, code, "meeting", conv.id)
    store.set_presence(db, roster.SUPERVISOR, "meeting", conv.id)
    store.record_event(
        db,
        conv.id,
        "discussion_started",
        actor=roster.SUPERVISOR,
        correlation_id=correlation,
        payload={"kind": kind, "rounds": rounds, "participants": speakers, "task_id": task_id},
    )
    if kind == "boardroom":
        rows += discussion.run_boardroom(
            db, conv, agenda=list(conv.agenda or []), correlation_id=correlation, task_id=task_id
        )
    else:
        rows += discussion.run_discussion(
            db,
            conv,
            topic=topic,
            participants=speakers,
            rounds=rounds,
            correlation_id=correlation,
            task_id=task_id,
        )
    for code in {*speakers, roster.SUPERVISOR}:
        store.set_presence(db, code, "idle", None)
    if rows and rows[-1].sender_kind == "agent":
        store.set_presence(db, rows[-1].sender_id, "speaking", conv.id)
    store.mark_read(db, conv.id, store.last_seq(db, conv.id))
    out = store.conversation_out(db, conv)
    messages = [store.message_out(r) for r in rows]
    db.commit()
    realtime = _announce(request, db, rows, correlation)
    return SendResult(conversation=out, messages=messages, realtime=realtime)  # type: ignore[arg-type]


@router.post("/triggers", response_model=SendResult)
@store_errors
def trigger_discussion(
    body: TriggerBody, request: Request, db: Session = Depends(get_db)
) -> SendResult:
    """Task-driven discussion. Off unless the autonomous_discussions flag is on."""

    _require(request, "autonomous_discussions")
    _throttle(request)
    marker = f"[auto:{body.task}] "
    latest = db.scalars(
        select(ConversationRow)
        .where(ConversationRow.created_by == "system", ConversationRow.topic.like(f"{marker}%"))
        .order_by(ConversationRow.created_at.desc())
        .limit(1)
    ).first()
    if latest is not None:
        created = (
            latest.created_at if latest.created_at.tzinfo else latest.created_at.replace(tzinfo=UTC)
        )
        if datetime.now(UTC) - created < AUTO_COOLDOWN:
            raise HTTPException(
                status_code=429, detail="Cooldown: this task ran in the last 15 minutes."
            )
    topic = marker + AUTO_TOPICS[body.task]
    return _run(request, db, topic, None, 2, "discussion", None, "system", _correlation())


@router.post("/conversations/{conversation_id}/moderate", response_model=SendResult)
@store_errors
def moderate(
    conversation_id: uuid.UUID, body: Moderate, request: Request, db: Session = Depends(get_db)
) -> SendResult:
    _throttle(request)
    _require(request, "group_chat")
    conv = _conversation(db, conversation_id)
    if conv.kind == "direct":
        raise HTTPException(status_code=422, detail="Direct chats are not moderated.")
    if conv.status == "archived":
        raise HTTPException(status_code=409, detail="Conversation is archived.")
    correlation = _correlation()
    note = safety.clean(body.note or "", 200)
    rows: list[MessageRow] = []

    def notice(text: str) -> MessageRow:
        return store.append_message(
            db,
            conv,
            sender_id=store.SYSTEM,
            sender_kind="system",
            content=text,
            kind="notice",
            origin="scripted",
            correlation_id=correlation,
            recipients=[],
        )

    action = body.action
    if action == "close":
        if conv.status == "closed":
            raise HTTPException(status_code=409, detail="Conversation is already closed.")
        counts: dict[str, int] = {}
        for row in store.replies_after(db, conv.id, 0):
            counts[row.kind] = counts.get(row.kind, 0) + 1
        conv.status = "closed"
        conv.closed_at = datetime.now(UTC)
        rows.append(
            notice(
                "Closed by the owner. "
                + (note + " " if note else "")
                + "No order or transfer was authorised."
            )
        )
        summary = ", ".join(f"{n} {k}" for k, n in sorted(counts.items())) or "no messages"
        rows.append(
            store.append_message(
                db,
                conv,
                sender_id=roster.SUPERVISOR,
                sender_kind="agent",
                kind="summary",
                origin="tool_verified",
                correlation_id=correlation,
                content=f"Closing summary from persisted messages: {summary}. "
                "Anything not stated above was not decided.",
                citations=[
                    Citation(
                        source="messages",
                        ref=str(conv.id),
                        label=f"{sum(counts.values())} persisted messages",
                    )
                ],
            )
        )
        store.add_summary(
            db, conv.id, store.last_seq(db, conv.id), rows[-1].content, "tool_verified"
        )
    elif action == "pause":
        if conv.status != "open":
            raise HTTPException(status_code=409, detail="Only an open conversation can pause.")
        conv.status = "paused"
        rows.append(notice("Paused by the owner. Desks will not reply until it resumes."))
    elif action == "resume":
        if conv.status != "paused":
            raise HTTPException(status_code=409, detail="Conversation is not paused.")
        conv.status = "open"
        rows.append(notice("Resumed by the owner."))
    elif action == "redirect":
        if not note:
            raise HTTPException(status_code=422, detail="redirect needs a note with the new topic.")
        conv.topic = note
        rows.append(notice(f"Topic redirected by the owner to: {note}"))
    elif action == "assign_owner":
        members = store.agent_members(db, conv.id)
        if body.agent_code not in members:
            raise HTTPException(status_code=422, detail="agent_code must be a member.")
        conv.owner_id = body.agent_code
        rows.append(
            notice(
                f"{roster.name_of(body.agent_code)} is the assigned owner. "
                "Assignment is a record. It starts no work."
            )
        )
    else:  # request_evidence
        members = store.agent_members(db, conv.id)
        if body.agent_code not in members:
            raise HTTPException(status_code=422, detail="agent_code must be a member.")
        rows.append(
            notice(
                f"The owner asked {roster.name_of(body.agent_code)} for evidence"
                + (f": {note}" if note else ".")
            )
        )
        reply = replies.compose_reply(
            db,
            body.agent_code,
            "show the latest data you hold on: " + (note or conv.topic),
            history=store.recent(db, conv.id, 12),
            brief=False,
        )
        rows.append(
            store.append_message(
                db,
                conv,
                sender_id=body.agent_code,
                sender_kind="agent",
                content=reply.content,
                kind="evidence" if reply.kind == "reply" else reply.kind,
                origin=reply.origin,
                correlation_id=correlation,
                recipients=[store.HUMAN],
                citations=reply.citations,
                meta=reply.meta,
                thread_id=rows[0].id,
            )
        )
    store.record_event(
        db,
        conv.id,
        f"moderated_{action}",
        actor=store.HUMAN,
        correlation_id=correlation,
        payload={"note": note},
    )
    conv.updated_at = datetime.now(UTC)
    out = store.conversation_out(db, conv)
    messages = [store.message_out(r) for r in rows]
    db.commit()
    realtime = _announce(request, db, rows, correlation)
    return SendResult(conversation=out, messages=messages, realtime=realtime)  # type: ignore[arg-type]


@router.post("/messages/{message_id}/answer", response_model=SendResult)
@store_errors
def answer_message(
    message_id: uuid.UUID, request: Request, db: Session = Depends(get_db)
) -> SendResult:
    """One other desk answers a stored line. Calling it again returns the same reply."""

    _throttle(request)
    _require(request, "agent_chat")
    source = db.get(MessageRow, message_id)
    if source is None or source.sender_kind != "agent":
        raise HTTPException(status_code=404, detail="Message not found.")
    conv = _conversation(db, source.conversation_id)
    row, created = replies.answer_line(db, source)
    if row is None:
        return SendResult(
            conversation=store.conversation_out(db, conv), messages=[], duplicate=True
        )
    out = store.conversation_out(db, conv)
    messages = [store.message_out(row)]
    if not created:
        return SendResult(conversation=out, messages=messages, duplicate=True)
    db.commit()
    realtime = _announce(request, db, [row], row.correlation_id)
    return SendResult(conversation=out, messages=messages, realtime=realtime)  # type: ignore[arg-type]


@router.post("/floor", response_model=SendResult)
@store_errors
def floor(request: Request, db: Session = Depends(get_db)) -> SendResult:
    """Each desk writes its paper-mode job in English. Nothing here submits an order."""

    _throttle(request)
    _require(request, "agent_chat")
    correlation = correlation_id_var.get() or uuid.uuid4().hex
    rows, created = work.record_floor(db, correlation)
    conv = store.get_conversation(db, rows[0].conversation_id) if rows else None
    if conv is None:
        raise HTTPException(status_code=503, detail=STORE_DOWN)
    out = store.conversation_out(db, conv)
    messages = [store.message_out(row) for row in rows]
    if not created:
        return SendResult(conversation=out, messages=messages, duplicate=True)
    db.commit()
    realtime = _announce(request, db, rows, correlation)
    return SendResult(conversation=out, messages=messages, realtime=realtime)  # type: ignore[arg-type]


@router.get("/feed", response_model=FeedResponse)
@store_errors
def feed(
    request: Request,
    limit: int = Query(default=40, ge=1, le=100),
    after: datetime | None = None,
    db: Session = Depends(get_db),
) -> FeedResponse:
    rows = store.feed(db, limit=limit, after=after)
    return FeedResponse(
        messages=[store.message_out(r) for r in rows],
        realtime=_notifier(request).status(),  # type: ignore[arg-type]
    )
