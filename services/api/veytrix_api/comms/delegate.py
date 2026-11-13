"""Roads assigns research. The summary may quote only stored replies.

No function here submits an order, signs, or transfers. A desk cannot claim it
researched a subject unless this module stored both the task and the reply.
"""

from __future__ import annotations

import re
import uuid

from sqlalchemy.orm import Session

from veytrix_api.claude_provider import acceptable, converse
from veytrix_api.comms import roster, safety, store, tasks
from veytrix_api.comms.envelope import Citation
from veytrix_api.models import ConversationRow, MessageRow, ResearchTaskRow

_ASSIGN = re.compile(
    r"\b(?:have|ask|tell|get|assign)\b.+?\bresearch\b\s+(?P<subject>.+)$",
    re.IGNORECASE | re.DOTALL,
)


def matches(text: str) -> bool:
    return _ASSIGN.search(text.strip()) is not None and not safety.wants_order(text)


def parse(text: str) -> tuple[list[str], str] | None:
    """Desk codes and a short subject. None when the sentence is not an assignment."""

    found = _ASSIGN.search(text.strip())
    if found is None or safety.wants_order(text):
        return None
    subject = re.sub(r"\s+", " ", found.group("subject")).strip(" .?!\"'")
    subject = subject[:80]
    if not subject or safety.wants_order(subject):
        return None
    desks = _named(text)
    if not desks:
        return None
    return desks, subject


def _named(text: str) -> list[str]:
    mentioned, everyone = roster.mentions(text)
    if everyone:
        return [code for code in roster.CODES if code != roster.SUPERVISOR]
    if mentioned:
        return [code for code in mentioned if code != roster.SUPERVISOR]
    lowered = text.lower()
    found: list[str] = []
    for desk in roster.DESKS:
        if desk.code == roster.SUPERVISOR:
            continue
        if re.search(rf"\b{re.escape(desk.name.lower())}\b", lowered):
            found.append(desk.code)
    return found


def _local_reply(name: str, subject: str) -> str:
    return (
        f"{name}: Roads assigned me {subject}. "
        "I have no stored source for it, so I have no findings to report. "
        "I will not invent any. No order is sent."
    )


def _reply_for(code: str, subject: str, task_id: str) -> tuple[str, str, dict[str, object]]:
    desk = roster.desk_for(code)
    local = _local_reply(desk.name, subject)
    facts = (
        f"Task {task_id} is assigned to {desk.name} ({code}). "
        f"Subject: {subject}. Status: assigned. "
        "No stored source and no external findings exist yet. "
        "Trading, signing, and transfers are off."
    )
    spoken = converse(
        code,
        f"You were assigned research on {subject}. What can you report?",
        facts=facts,
    )
    meta: dict[str, object] = {
        "intent": "research_report",
        "language": "en",
        "task_id": task_id,
        "subject": subject,
        "external_research": False,
    }
    if spoken.origin == "model_generated" and acceptable(spoken.text):
        meta["model"] = spoken.model or "claude"
        meta["streamed"] = spoken.chunks > 1
        meta["chunk_count"] = spoken.chunks
        return spoken.text, "model_generated", meta
    meta["model"] = "disconnected" if spoken.error_class != "missing_key" else "not_configured"
    if spoken.error_class:
        meta["error_class"] = spoken.error_class
    meta["fallback"] = "scripted"
    return local, "scripted", meta


def assign(
    db: Session,
    conv: ConversationRow,
    text: str,
    correlation_id: str,
    thread_id: uuid.UUID | None,
) -> list[MessageRow]:
    """Create task rows, store each desk's reply, then quote those replies."""

    parsed = parse(text)
    if parsed is None:
        raise store.StoreError("Name the desks and the research subject. No order was sent.")
    codes, subject = parsed
    if store.message_count(db, conv.id) + 1 + (len(codes) * 2) > conv.max_messages:
        raise store.StoreError("This conversation is full. No order was sent.")

    created: list[tuple[str, ResearchTaskRow]] = []
    for code in codes:
        created.append(
            (
                code,
                tasks.create(
                    db,
                    assignee_code=code,
                    subject=subject,
                    instruction=f"Research {subject}. Report only stored evidence.",
                    conversation_id=conv.id,
                ),
            )
        )

    names = ", ".join(roster.name_of(code) for code in codes)
    assignment = store.append_message(
        db,
        conv,
        sender_id=roster.SUPERVISOR,
        sender_kind="agent",
        content=(
            f"I assigned {names} to research {subject}. "
            "Each desk will answer from stored records only. No order is sent."
        ),
        kind="assignment",
        origin="tool_verified",
        correlation_id=correlation_id,
        recipients=codes,
        thread_id=thread_id,
        citations=[
            Citation(source="research_tasks", ref=str(task.id), label=f"{code} assigned {subject}")
            for code, task in created
        ],
        meta={
            "intent": "delegate",
            "language": "en",
            "model": "not_configured",
            "subject": subject,
            "assignees": codes,
        },
    )

    replies: list[tuple[str, MessageRow]] = []
    for code, task in created:
        content, origin, meta = _reply_for(code, subject, str(task.id))
        row = store.append_message(
            db,
            conv,
            sender_id=code,
            sender_kind="agent",
            content=content,
            kind="reply",
            origin=origin,
            correlation_id=correlation_id,
            recipients=[roster.SUPERVISOR, store.HUMAN],
            thread_id=assignment.id,
            citations=[
                Citation(
                    source="research_tasks",
                    ref=str(task.id),
                    label=f"Assigned task {subject}",
                )
            ],
            meta=meta,
            task_id=str(task.id),
        )
        tasks.mark_reported(db, task, row.id)
        replies.append((code, row))

    quoted = []
    for code, row in replies:
        if row.id is None or not row.content:
            continue
        quoted.append(f"{roster.name_of(code)} ({row.origin}): {row.content}")
    summary_text = (
        f"Summary for {subject}. I am quoting stored replies only. "
        + " ".join(quoted)
        + " No desk reported an external finding. No order is sent."
    )
    summary = store.append_message(
        db,
        conv,
        sender_id=roster.SUPERVISOR,
        sender_kind="agent",
        content=safety.clean(summary_text, 3900),
        kind="summary",
        origin="tool_verified",
        correlation_id=correlation_id,
        recipients=[store.HUMAN],
        thread_id=assignment.id,
        citations=[
            Citation(source="messages", ref=str(row.id), label=f"{roster.name_of(code)} reply")
            for code, row in replies
        ],
        meta={
            "intent": "delegate_summary",
            "language": "en",
            "model": "not_configured",
            "subject": subject,
            "evidence_message_ids": [str(row.id) for _, row in replies],
            "external_research": False,
        },
    )
    _copy_to_group(db, subject, correlation_id, assignment, replies, summary)
    return [assignment, *[row for _, row in replies], summary]


def _copy_to_group(
    db: Session,
    subject: str,
    correlation_id: str,
    assignment: MessageRow,
    replies: list[tuple[str, MessageRow]],
    summary: MessageRow,
) -> None:
    """A second transcript so the desks have the exchange after the founder leaves."""

    agents = [roster.SUPERVISOR, *[code for code, _row in replies]]
    group = store.create_conversation(
        db,
        kind="group",
        title=f"Research: {subject}"[:120],
        topic=f"Roads assigned research on {subject}. Quotes only stored replies.",
        agents=agents,
        created_by="system",
        max_messages=200,
        moderator=roster.SUPERVISOR,
    )
    copies = [assignment, *[row for _, row in replies], summary]
    for source in copies:
        store.append_message(
            db,
            group,
            sender_id=source.sender_id,
            sender_kind=source.sender_kind,
            content=source.content,
            kind=source.kind,
            origin=source.origin,
            correlation_id=correlation_id,
            recipients=list(source.recipient_ids or []),
            citations=[],
            meta={**(source.meta or {}), "copied_from": str(source.id)},
            task_id=source.task_id,
        )
