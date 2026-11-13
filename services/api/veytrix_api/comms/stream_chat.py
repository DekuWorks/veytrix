"""Server-sent chat events. Chunks are yielded before the reply row is stored.

A model label is applied only by `replies.apply_speech`, which requires a
provider message id. This module does not submit an order.
"""

from __future__ import annotations

import json
from collections.abc import Iterator

from sqlalchemy.orm import Session

from veytrix_api.claude_provider import Speech, stream_converse
from veytrix_api.comms import delegate, replies, roster, store, work
from veytrix_api.comms.envelope import SendMessage, SendResult
from veytrix_api.models import ConversationRow, MessageRow


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def iter_chat_events(
    db: Session,
    conv: ConversationRow,
    body: SendMessage,
    correlation: str,
    responders: list[str],
) -> Iterator[str]:
    if body.client_message_id:
        prior = store.find_by_client_id(db, conv.id, body.client_message_id)
        if prior is not None:
            again = [prior, *store.replies_after(db, conv.id, prior.seq)]
            yield sse("done", _result(db, conv, again, duplicate=True))
            return

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
    rows: list[MessageRow] = [human]
    if conv.status == "paused":
        db.commit()
        yield sse("done", _result(db, conv, rows, held="paused"))
        return

    thread = body.thread_id or human.id
    if roster.SUPERVISOR in responders and delegate.matches(body.content):
        parsed = delegate.parse(body.content)
        if parsed is not None:
            rows.extend(delegate.assign(db, conv, body.content, correlation, thread))
            db.commit()
            yield sse("done", _result(db, conv, rows))
            return

    if len(responders) == 1 and replies.classify(body.content) == "working_on":
        code = responders[0]
        made = work.report(db, code, brief=False)
        spoken: Speech | None = None
        sent_chunk = False
        for kind, payload in stream_converse(code, body.content, facts=made.content):
            if kind == "chunk" and isinstance(payload, str) and payload:
                sent_chunk = True
                yield sse("chunk", {"text": payload, "sender": code})
            elif kind == "final" and isinstance(payload, Speech):
                spoken = payload
        if spoken is None:
            spoken = Speech(
                origin="simulated",
                text="",
                claude="disconnected",
                connected=False,
                error_class="empty_completion",
            )
        reply = replies.apply_speech(
            made,
            spoken,
            {"language": "en", "intent": "working_on"},
            registry_ok=made.status in {"enabled", "paused", "disabled"},
        )
        if not sent_chunk:
            yield sse("chunk", {"text": reply.content, "sender": code})
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
        rows.append(row)
        db.commit()
        yield sse("done", _result(db, conv, rows))
        return

    for code in responders:
        if store.message_count(db, conv.id) >= conv.max_messages:
            break
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
        rows.append(row)
    db.commit()
    yield sse("done", _result(db, conv, rows))


def _result(
    db: Session,
    conv: ConversationRow,
    rows: list[MessageRow],
    *,
    duplicate: bool = False,
    held: str | None = None,
) -> dict:
    payload = SendResult(
        conversation=store.conversation_out(db, conv),
        messages=[store.message_out(row) for row in rows],
        duplicate=duplicate,
        held=held,
    )
    return payload.model_dump(mode="json")
