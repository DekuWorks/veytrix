"""Durable research worker. One process, one task at a time, no browser timer.

The worker claims queued rows, writes heartbeats, and stores replies. It does
not submit an order, sign, or transfer. A research task is completed only when
a stored source mentions the subject and the reply cites that source.
"""

from __future__ import annotations

import os
import signal
import sys
import time
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from urllib.parse import urlparse

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from veytrix_api.claude_provider import Speech, credential_present, stream_converse
from veytrix_api.comms import delegate, roster, safety, store, tasks
from veytrix_api.comms.envelope import Citation
from veytrix_api.db import create_db_engine
from veytrix_api.models import (
    ConversationRow,
    MessageRow,
    ModelCallRow,
    ResearchNoteRow,
    ResearchTaskRow,
    SourceEventRow,
    TaskEventRow,
)
from veytrix_api.settings import BootRefused, get_settings

HEARTBEAT_SECONDS = 30
STALE_SECONDS = 90
DAILY_CALLS = 12
DAILY_USD = Decimal("0.12")
CALL_USD = Decimal("0.01")
TRANSIENT_PREFIXES = ("HTTPError", "URLError", "TimeoutError", "provider_error", "empty_completion")


def _now() -> datetime:
    return datetime.now(UTC)


def assert_veytrix_database() -> None:
    settings = get_settings()
    port = urlparse(settings.database_url).port
    if port == 5432:
        raise BootRefused("Refusing to boot: port 5432 is not the Veytrix database.")


def local_evidence(db: Session, subject: str) -> list[Citation]:
    """Notes and source events whose text names the subject. Nothing is invented."""

    needle = subject.strip().lower()
    if len(needle) < 2:
        return []
    found: list[Citation] = []
    for note in db.scalars(select(ResearchNoteRow)).all():
        blob = f"{note.title}\n{note.body}"
        if needle in blob.lower() and not safety.looks_like_instruction(note.body):
            found.append(Citation(source="research_notes", ref=str(note.id), label=note.title[:80]))
    for event in db.scalars(select(SourceEventRow)).all():
        if needle in event.title.lower() and not safety.looks_like_instruction(event.title):
            found.append(
                Citation(source="source_events", ref=str(event.id), label=event.title[:80])
            )
    return found[:5]


def _event(db: Session, task_id: uuid.UUID, kind: str, body: str) -> None:
    db.add(
        TaskEventRow(
            id=uuid.uuid4(),
            task_id=task_id,
            kind=kind,
            body=safety.clean(body, 500) or "update",
            created_at=_now(),
        )
    )
    db.flush()


def beat(
    db: Session,
    code: str,
    lifecycle: str,
    worker_id: str,
    task_id: uuid.UUID | None = None,
) -> None:
    """A heartbeat is a timestamp from this worker. Chat presence is left alone."""

    from veytrix_api.models import AgentPresenceRow

    row = db.get(AgentPresenceRow, code)
    now = _now()
    if row is None:
        db.add(
            AgentPresenceRow(
                agent_code=code,
                state="idle",
                conversation_id=None,
                lifecycle=lifecycle,
                heartbeat_at=now,
                worker_id=worker_id,
                task_id=task_id,
                updated_at=now,
            )
        )
    else:
        row.lifecycle = lifecycle
        row.heartbeat_at = now
        row.worker_id = worker_id
        row.task_id = task_id
        row.updated_at = now
    db.flush()


def beat_floor(db: Session, worker_id: str) -> None:
    latest = {
        row.assignee_code: row
        for row in db.scalars(
            select(ResearchTaskRow).order_by(ResearchTaskRow.created_at.desc())
        ).all()
    }
    seen: set[str] = set()
    for row in latest.values():
        if row.assignee_code in seen:
            continue
        seen.add(row.assignee_code)
        if row.status == "running" and row.worker_id == worker_id:
            lifecycle = "working"
        elif row.status == "queued":
            lifecycle = "queued"
        elif row.status == "blocked":
            lifecycle = "blocked"
        elif row.status == "failed":
            lifecycle = "failed"
        else:
            lifecycle = "idle"
        beat(
            db, row.assignee_code, lifecycle, worker_id, row.id if row.status == "running" else None
        )
    for code in roster.CODES:
        if code not in seen:
            beat(db, code, "idle", worker_id, None)


def fresh(
    heartbeat_at: datetime | None, worker_id: str | None, now: datetime | None = None
) -> bool:
    if heartbeat_at is None or not worker_id:
        return False
    current = now or _now()
    moment = heartbeat_at if heartbeat_at.tzinfo else heartbeat_at.replace(tzinfo=UTC)
    return (current - moment).total_seconds() <= HEARTBEAT_SECONDS


def recover_stale(db: Session) -> int:
    cutoff = _now() - timedelta(seconds=STALE_SECONDS)
    recovered = 0
    rows = db.scalars(select(ResearchTaskRow).where(ResearchTaskRow.status == "running")).all()
    for task in rows:
        updated = task.updated_at if task.updated_at.tzinfo else task.updated_at.replace(tzinfo=UTC)
        if updated >= cutoff:
            continue
        _event(db, task.id, "retry", "The worker stopped while this task was running.")
        tasks.requeue(db, task)
        recovered += 1
    return recovered


def _budget_open(db: Session) -> bool:
    since = _now() - timedelta(hours=24)
    count, spent = db.execute(
        select(
            func.count(),
            func.coalesce(func.sum(ModelCallRow.estimated_usd), 0),
        ).where(ModelCallRow.created_at >= since)
    ).one()
    return int(count) < DAILY_CALLS and Decimal(spent) < DAILY_USD


def _record_call(db: Session, code: str, spoken: Speech) -> None:
    if not spoken.networked:
        return
    db.add(
        ModelCallRow(
            id=uuid.uuid4(),
            agent_code=code,
            model=(spoken.model or "claude-haiku-4-5")[:64],
            provider_message_id=spoken.provider_message_id,
            estimated_usd=CALL_USD,
            error_class=spoken.error_class,
            created_at=_now(),
        )
    )
    db.flush()


def _transient(error_class: str | None) -> bool:
    if not error_class:
        return False
    if error_class in {"HTTPError:401", "HTTPError:403", "missing_key", "budget_exhausted"}:
        return False
    return error_class.startswith(TRANSIENT_PREFIXES)


def _claim(db: Session, worker_id: str, kind: str) -> ResearchTaskRow | None:
    rows = db.scalars(
        select(ResearchTaskRow)
        .where(ResearchTaskRow.status == "queued", ResearchTaskRow.kind == kind)
        .order_by(ResearchTaskRow.created_at)
        .limit(4)
        .with_for_update(skip_locked=True)
    ).all()
    for task in rows:
        if kind == "review" and _research_open(db, task):
            continue
        task.status = "running"
        task.worker_id = worker_id
        task.updated_at = _now()
        _event(db, task.id, "state", "running")
        db.flush()
        return task
    return None


def _research_open(db: Session, review: ResearchTaskRow) -> bool:
    count = db.scalar(
        select(func.count())
        .select_from(ResearchTaskRow)
        .where(
            ResearchTaskRow.correlation_id == review.correlation_id,
            ResearchTaskRow.kind == "research",
            ResearchTaskRow.status.in_(("queued", "running")),
        )
    )
    return bool(count)


def _siblings(db: Session, task: ResearchTaskRow) -> list[ResearchTaskRow]:
    return list(
        db.scalars(
            select(ResearchTaskRow).where(ResearchTaskRow.correlation_id == task.correlation_id)
        ).all()
    )


def _contradicts(text: str, local: str) -> bool:
    """A completion that denies the stored task cannot be saved as the finding."""

    lowered = text.lower()
    local_lower = local.lower()
    if "no task is assigned" in lowered and ("blocked" in local_lower or "task" in local_lower):
        return True
    if (
        "cannot provide a review" in lowered
        or "cannot review" in lowered
        or "nothing to review" in lowered
    ):
        return True
    return False


def _gap_text(name: str, subject: str) -> str:
    return (
        f"{name}: I have no stored source for {subject}, so I have no findings. "
        "This stays blocked. I will not invent a price or a filing. No order is sent."
    )


def _finding_text(name: str, subject: str, label: str) -> str:
    return (
        f"{name}: The stored record {label} mentions {subject}. "
        "I am not adding a price, a filing, or a news item. No order is sent."
    )


def _review_text(subject: str, siblings: list[ResearchTaskRow]) -> str:
    research = [row for row in siblings if row.kind == "research"]
    blocked = [roster.name_of(row.assignee_code) for row in research if row.status != "completed"]
    verified = [roster.name_of(row.assignee_code) for row in research if row.status == "completed"]
    if verified and not blocked:
        names = ", ".join(verified)
        return (
            f"Aegis: I reviewed the stored {subject} tasks. {names} cited a stored record. "
            "The limitation is that this is not a live market check. No order is sent."
        )
    if verified and blocked:
        return (
            f"Aegis: I reviewed the stored {subject} tasks. "
            f"Verified records: {', '.join(verified)}. "
            f"Blocked or failed: {', '.join(blocked)}. "
            "I am not adding a price. No order is sent."
        )
    names = ", ".join(blocked) or "The research desks"
    return (
        f"Aegis: I reviewed the stored {subject} tasks. {names} "
        "are blocked or failed because no stored source exists. "
        "The limitation is that there is no verified market finding. No order is sent."
    )


def _speak(
    db: Session,
    code: str,
    prompt: str,
    facts: str,
    task: ResearchTaskRow,
    transport,
) -> Speech:
    if transport is None and not credential_present():
        final = Speech(
            origin="simulated",
            text="",
            claude="disconnected",
            connected=False,
            error_class="missing_key",
            networked=False,
        )
        return final
    if transport is None and not _budget_open(db):
        return Speech(
            origin="simulated",
            text="",
            claude="disconnected",
            connected=False,
            error_class="budget_exhausted",
            networked=False,
        )
    spoken: Speech | None = None
    for kind, payload in stream_converse(code, prompt, facts=facts, transport=transport):
        if kind == "chunk" and isinstance(payload, str) and payload.strip():
            _event(db, task.id, "chunk", payload.strip())
            db.commit()
        elif kind == "final" and isinstance(payload, Speech):
            spoken = payload
    if spoken is None:
        spoken = Speech(
            origin="simulated",
            text="",
            claude="disconnected",
            connected=False,
            error_class="empty_completion",
            networked=False,
        )
    if transport is None:
        _record_call(db, code, spoken)
    return spoken


def _store_reply(
    db: Session,
    task: ResearchTaskRow,
    content: str,
    origin: str,
    citations: list[Citation],
    meta: dict[str, object],
) -> MessageRow | None:
    conv = db.get(ConversationRow, task.conversation_id) if task.conversation_id else None
    if conv is None or store.message_count(db, conv.id) >= conv.max_messages:
        tasks.mark_failed(db, task, "conversation_full")
        return None
    parent = db.scalars(
        select(MessageRow)
        .where(
            MessageRow.conversation_id == conv.id,
            MessageRow.kind == "assignment",
            MessageRow.correlation_id == task.correlation_id,
        )
        .order_by(MessageRow.seq)
        .limit(1)
    ).first()
    return store.append_message(
        db,
        conv,
        sender_id=task.assignee_code,
        sender_kind="agent",
        content=safety.clean(content, 3900),
        kind="risk_assessment" if task.kind == "review" else "reply",
        origin=origin,
        correlation_id=task.correlation_id or "worker",
        recipients=[roster.SUPERVISOR, store.HUMAN],
        thread_id=parent.id if parent is not None else None,
        citations=citations,
        meta=meta,
        task_id=str(task.id),
    )


def _meta(task: ResearchTaskRow, spoken: Speech, fallback: str) -> dict[str, object]:
    meta: dict[str, object] = {
        "intent": "research_report" if task.kind == "research" else "risk_review",
        "language": "en",
        "task_id": str(task.id),
        "subject": task.subject,
        "external_research": False,
    }
    if spoken.origin == "model_generated" and spoken.provider_message_id:
        meta["model"] = spoken.model or "claude"
        meta["provider"] = "anthropic"
        meta["provider_message_id"] = spoken.provider_message_id
        meta["input_tokens"] = spoken.input_tokens
        meta["output_tokens"] = spoken.output_tokens
        meta["streamed"] = spoken.chunks > 0
        meta["chunk_count"] = spoken.chunks
        return meta
    meta["model"] = (
        "disconnected" if spoken.error_class not in {None, "missing_key"} else "not_configured"
    )
    meta["fallback"] = fallback
    if spoken.error_class:
        meta["error_class"] = spoken.error_class
    return meta


def run_task(db: Session, task: ResearchTaskRow, *, transport=None, worker_id: str) -> None:
    beat(db, task.assignee_code, "working", worker_id, task.id)
    db.commit()
    name = roster.name_of(task.assignee_code)
    evidence = local_evidence(db, task.subject) if task.kind == "research" else []
    siblings = _siblings(db, task)
    if task.kind == "review":
        facts = (
            f"Subject {task.subject}. "
            + (
                " ".join(
                    f"{row.assignee_code} is {row.status}, reason {row.blocked_reason or 'none'}."
                    for row in siblings
                    if row.kind == "research"
                )
                or "No research task is stored."
            )
            + " These stored rows are the evidence. Do not say that no task is assigned."
        )
        prompt = f"Review the risks and limitations of the {task.subject} research."
        local = _review_text(task.subject, siblings)
        citations = [
            Citation(
                source="research_tasks", ref=str(row.id), label=f"{row.assignee_code} {row.status}"
            )
            for row in siblings
            if row.id != task.id
        ]
    else:
        facts = (
            "Stored sources: " + "; ".join(item.label for item in evidence)
            if evidence
            else f"No stored source for {task.subject}."
        )
        prompt = f"What can you report about {task.subject} from the stored records?"
        local = (
            _finding_text(name, task.subject, evidence[0].label)
            if evidence
            else _gap_text(name, task.subject)
        )
        citations = evidence

    spoken = _speak(db, task.assignee_code, prompt, facts, task, transport)
    if _transient(spoken.error_class):
        _event(db, task.id, "retry", spoken.error_class or "retry")
        tasks.requeue(db, task)
        if task.status == "failed":
            _store_reply(
                db,
                task,
                f"{name}: The model call failed, so this task failed. No order is sent.",
                "simulated",
                citations,
                {
                    "intent": "research_report",
                    "language": "en",
                    "model": "disconnected",
                    "error_class": spoken.error_class,
                    "fallback": "scripted",
                    "external_research": False,
                },
            )
        db.commit()
        return

    use_model = (
        spoken.origin == "model_generated"
        and bool(spoken.provider_message_id)
        and not _contradicts(spoken.text, local)
    )
    content = local
    origin = "scripted"
    meta_speech = spoken
    if use_model:
        content = spoken.text
        origin = "model_generated"
    elif spoken.origin == "model_generated":
        meta_speech = Speech(
            origin="simulated",
            text="",
            claude="disconnected",
            connected=False,
            error_class="contradicted_record",
            networked=spoken.networked,
        )
    elif spoken.error_class and spoken.error_class not in {None, "missing_key"}:
        origin = (
            "simulated"
            if spoken.error_class not in {"unsupported_claim", "missing_provider_id"}
            else "scripted"
        )
    row = _store_reply(db, task, content, origin, citations, _meta(task, meta_speech, "scripted"))
    if row is None:
        db.commit()
        return
    findings = [item for item in siblings if item.kind == "research" and item.status == "completed"]
    if task.kind == "review" and findings and citations:
        tasks.mark_completed(db, task, row.id)
    elif task.kind == "research" and evidence:
        tasks.mark_completed(db, task, row.id)
    else:
        if task.kind == "review" and not findings:
            reason = "no_findings"
        elif not evidence:
            reason = "no_stored_source"
        else:
            reason = spoken.error_class or "no_evidence"
        tasks.mark_blocked(db, task, row.id, reason)
    _event(db, task.id, "state", task.status)
    db.commit()


def _summarize(db: Session, correlation_id: str | None) -> None:
    if not correlation_id:
        return
    rows = list(
        db.scalars(
            select(ResearchTaskRow).where(ResearchTaskRow.correlation_id == correlation_id)
        ).all()
    )
    if not rows or any(row.status in ("queued", "running") for row in rows):
        return
    conv_id = rows[0].conversation_id
    if conv_id is None:
        return
    existing = db.scalars(
        select(MessageRow).where(
            MessageRow.conversation_id == conv_id,
            MessageRow.kind == "summary",
            MessageRow.correlation_id == correlation_id,
        )
    ).first()
    if existing is not None:
        return
    conv = db.get(ConversationRow, conv_id)
    if conv is None or store.message_count(db, conv.id) >= conv.max_messages:
        return
    subject = rows[0].subject
    research = [row for row in rows if row.kind == "research"]
    review = next((row for row in rows if row.kind == "review"), None)
    verified: list[str] = []
    blocked: list[str] = []
    citations: list[Citation] = []
    for row in research:
        label = roster.name_of(row.assignee_code)
        if row.status == "completed" and row.evidence_message_id:
            message = db.get(MessageRow, row.evidence_message_id)
            quote = safety.clean(message.content, 160) if message is not None else ""
            verified.append(f"{label}: {quote}")
            citations.append(
                Citation(source="messages", ref=str(row.evidence_message_id), label=label)
            )
        else:
            blocked.append(f"{label} ({row.status})")
    aegis_bit = ""
    if review is not None and review.evidence_message_id:
        message = db.get(MessageRow, review.evidence_message_id)
        if message is not None:
            aegis_bit = f" Aegis ({message.origin}): {safety.clean(message.content, 220)}"
            citations.append(Citation(source="messages", ref=str(message.id), label="Aegis review"))
    if verified:
        found = "Verified findings: " + " ".join(verified)
    else:
        found = "Verified findings: none."
    held = f" Blocked or failed: {', '.join(blocked)}." if blocked else ""
    text = (
        f"{subject} review. {found}{held}{aegis_bit} "
        "I am quoting stored replies only. No order is sent."
    )
    parent = db.scalars(
        select(MessageRow)
        .where(
            MessageRow.conversation_id == conv.id,
            MessageRow.kind == "assignment",
            MessageRow.correlation_id == correlation_id,
        )
        .limit(1)
    ).first()
    summary = store.append_message(
        db,
        conv,
        sender_id=roster.SUPERVISOR,
        sender_kind="agent",
        content=safety.clean(text, 3900),
        kind="summary",
        origin="tool_verified",
        correlation_id=correlation_id,
        recipients=[store.HUMAN],
        thread_id=parent.id if parent is not None else None,
        citations=citations,
        meta={
            "intent": "delegate_summary",
            "language": "en",
            "model": "not_configured",
            "subject": subject,
            "external_research": False,
            "verified_count": len(verified),
            "blocked_count": len(blocked),
        },
    )
    stored = [row for row in [parent, summary] if row is not None]
    replies = list(
        db.scalars(
            select(MessageRow).where(
                MessageRow.conversation_id == conv.id,
                MessageRow.correlation_id == correlation_id,
                MessageRow.kind.in_(("reply", "risk_assessment")),
            )
        ).all()
    )
    delegate.copy_exchange(db, subject, correlation_id, [*stored, *replies])
    db.commit()


def drain(db: Session, *, transport=None, worker_id: str = "local", limit: int = 6) -> list[str]:
    """Claim and finish up to `limit` tasks. Safe to call when the browser is closed."""

    recover_stale(db)
    done: list[str] = []
    for _ in range(limit):
        task = _claim(db, worker_id, "research") or _claim(db, worker_id, "review")
        if task is None:
            break
        correlation = task.correlation_id
        run_task(db, task, transport=transport, worker_id=worker_id)
        done.append(str(task.id))
        _summarize(db, correlation)
    beat_floor(db, worker_id)
    db.commit()
    return done


def main() -> None:
    """Loop until SIGINT or SIGTERM. `--once` still drains a single batch for tests."""

    assert_veytrix_database()
    once = "--once" in sys.argv
    stop = False

    def _stop(_signum: int, _frame: object) -> None:
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)
    engine = create_db_engine(get_settings())
    worker_id = f"local-{os.getpid()}"
    while not stop:
        with Session(engine) as db:
            drain(db, worker_id=worker_id)
        if once or stop:
            return
        for _ in range(4):
            if stop:
                return
            time.sleep(0.5)


if __name__ == "__main__":
    main()
