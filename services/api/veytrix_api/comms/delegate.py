"""Roads queues research. The worker writes the replies. This module does not.

No function here submits an order, signs, or transfers. A desk cannot claim it
researched a subject unless a task row and a reply row both exist.
"""

from __future__ import annotations

import re
import uuid

from sqlalchemy.orm import Session

from veytrix_api.comms import roster, safety, store, tasks
from veytrix_api.comms.envelope import Citation
from veytrix_api.models import ConversationRow, MessageRow, ResearchTaskRow

_ASSIGN = re.compile(
    r"\b(?:have|ask|tell|get|assign)\b.+?\bresearch\b\s+(?P<subject>.+)$",
    re.IGNORECASE | re.DOTALL,
)
_COORD = re.compile(
    r"\bcoordinate\b\s+(?:an?\s+|the\s+)?(?P<subject>[A-Za-z0-9][\w.&-]{0,40})"
    r"\s+research\s+review\b",
    re.IGNORECASE,
)
_COORD_OF = re.compile(
    r"\bcoordinate\b.+\bresearch\s+review\s+(?:of|on|for)\s+(?P<subject>[A-Za-z0-9][\w.& -]{0,40})",
    re.IGNORECASE,
)
MAX_ASSIGNEES = 3


def matches(text: str) -> bool:
    stripped = text.strip()
    if safety.wants_order(stripped):
        return False
    return _ASSIGN.search(stripped) is not None or _subject(stripped) is not None


def _subject(text: str) -> str | None:
    found = _COORD.search(text) or _COORD_OF.search(text) or _ASSIGN.search(text)
    if found is None:
        return None
    subject = re.sub(r"\s+", " ", found.group("subject")).strip(" .?!\"'")
    subject = re.sub(r"^(?:an|a|the)\s+", "", subject, flags=re.IGNORECASE)
    subject = subject[:80]
    if not subject or safety.wants_order(subject):
        return None
    return subject


def _named(text: str) -> list[str]:
    mentioned, everyone = roster.mentions(text)
    if everyone:
        return [code for code in roster.CODES if code not in {roster.SUPERVISOR, roster.RISK}]
    if mentioned:
        return [code for code in mentioned if code not in {roster.SUPERVISOR, roster.RISK}]
    lowered = text.lower()
    found: list[str] = []
    for desk in roster.DESKS:
        if desk.code in {roster.SUPERVISOR, roster.RISK}:
            continue
        if re.search(rf"\b{re.escape(desk.name.lower())}\b", lowered):
            found.append(desk.code)
    return found


def parse(text: str) -> tuple[list[str], str] | None:
    """At most two research desks plus Aegis. None when this is not an assignment."""

    stripped = text.strip()
    if safety.wants_order(stripped):
        return None
    subject = _subject(stripped)
    if subject is None:
        return None
    named = _named(stripped)
    research = named[:2] if named else ["RESEARCH-01", "DEFI-01"]
    codes: list[str] = []
    for code in [*research, roster.RISK]:
        if code not in codes:
            codes.append(code)
    return codes[:MAX_ASSIGNEES], subject


def assign(
    db: Session,
    conv: ConversationRow,
    text: str,
    correlation_id: str,
    thread_id: uuid.UUID | None,
) -> list[MessageRow]:
    """Queue the tasks and store Roads's assignment. Replies come from the worker."""

    parsed = parse(text)
    if parsed is None:
        raise store.StoreError("Name the research subject. No order was sent.")
    codes, subject = parsed
    if store.message_count(db, conv.id) + 2 > conv.max_messages:
        raise store.StoreError("This conversation is full. No order was sent.")

    created: list[tuple[str, ResearchTaskRow]] = []
    for code in codes:
        kind = "review" if code == roster.RISK else "research"
        instruction = (
            f"Review the risks and limitations of {subject}. Use only stored task rows."
            if kind == "review"
            else f"Research {subject}. Report only stored evidence."
        )
        created.append(
            (
                code,
                tasks.create(
                    db,
                    assignee_code=code,
                    subject=subject,
                    instruction=instruction,
                    conversation_id=conv.id,
                    kind=kind,
                    correlation_id=correlation_id,
                ),
            )
        )

    research_names = ", ".join(
        roster.name_of(code) for code, task in created if task.kind == "research"
    )
    assignment = store.append_message(
        db,
        conv,
        sender_id=roster.SUPERVISOR,
        sender_kind="agent",
        content=(
            f"I queued {research_names} to research {subject}, and I asked Aegis to review "
            "the risks separately. They will answer from stored records only. No order is sent."
        ),
        kind="assignment",
        origin="tool_verified",
        correlation_id=correlation_id,
        recipients=codes,
        thread_id=thread_id,
        citations=[
            Citation(source="research_tasks", ref=str(task.id), label=f"{code} queued {subject}")
            for code, task in created
        ],
        meta={
            "intent": "delegate",
            "language": "en",
            "model": "not_configured",
            "subject": subject,
            "assignees": codes,
            "external_research": False,
        },
    )
    return [assignment]


def copy_exchange(
    db: Session,
    subject: str,
    correlation_id: str,
    messages: list[MessageRow],
) -> None:
    """A second transcript so the desks keep the exchange after the founder leaves."""

    agents = list(dict.fromkeys([roster.SUPERVISOR, *[row.sender_id for row in messages]]))
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
    for source in messages:
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
