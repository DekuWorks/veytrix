"""English reports of what each desk actually read.

Language is English (`en`). The words are assembled from local records, so the
origin is `tool_verified`. This module does not call a model, MAC-01, Alpaca,
or the swap CLI, and it cannot submit an order.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from veytrix_api.comms import facts as fx
from veytrix_api.comms import roster, safety, store, tasks
from veytrix_api.comms.envelope import Citation
from veytrix_api.models import AgentRow, AgentRunRow, ConversationRow, MessageRow, ResearchTaskRow

LANGUAGE = "en"
FLOOR_TITLE = "Floor work"
NO_ORDER = "No order is sent. Trading, signing, and transfers stay off."

# Plain work, not a registry dump. None of these sentences contain "disabled".
JOB: dict[str, str] = {
    "SUPERVISOR-01": "I coordinate the floor and assign research.",
    "DAY-01": "I read the session ledger.",
    "STOCK-01": "I read stored SMA signals.",
    "CRYPTO-01": "I read stored price bars.",
    "DEFI-01": "I read paper swaps. I cannot sign.",
    "ETF-01": "I read stored ETF instruments.",
    "RESEARCH-01": "I read notes and source events.",
    "RISK-01": "I read the paper risk policy.",
    "TREASURY-01": "I read paper fills. I cannot move funds.",
    "FUTURES-01": "I read futures labels only. No Topstep account is connected.",
}


class Report:
    def __init__(
        self,
        content: str,
        citations: list[Citation],
        *,
        status: str,
    ) -> None:
        self.content = content
        self.citations = citations
        self.status = status
        self.meta: dict[str, object] = {
            "desk_task": True,
            "language": LANGUAGE,
            "model": "not_configured",
            "intent": "desk_task",
            "registry_status": status,
        }


def _availability(status: str) -> str:
    if status == "enabled":
        return "I'm available for paper research."
    if status == "paused":
        return "I'm paused, so I'm not taking new work."
    if status == "disabled":
        return "This desk is not taking work."
    return "I could not read my availability."


def _task_sentence(rows: list[ResearchTaskRow]) -> str:
    if not rows:
        return "No task is assigned to me."
    latest = rows[0]
    extra = f" {len(rows)} tasks are on my list." if len(rows) > 1 else ""
    return f"My latest assigned task is {latest.subject}, and it is {latest.status}.{extra}"


def _activity(db: Session, code: str) -> str:
    row = db.scalars(
        select(MessageRow)
        .where(MessageRow.sender_id == code, MessageRow.sender_kind == "agent")
        .order_by(MessageRow.created_at.desc())
        .limit(1)
    ).first()
    if row is None:
        return "I have no recent stored activity."
    snippet = safety.clean(row.content, 120)
    if "disabled" in snippet.lower() or safety.looks_like_instruction(snippet):
        return "I have a stored note. The technical wording is in diagnostics."
    return f"My last stored note starts: {snippet}"


def _registry_status(facts: list[fx.Fact]) -> str:
    row = next((fact for fact in facts if fact.key == "registry"), None)
    if row is None:
        return "unread"
    text = row.text
    for word in ("enabled", "paused", "disabled"):
        if f"status is {word}" in text:
            return word
    return "unread"


def report(db: Session, code: str, *, brief: bool = False) -> Report:
    """One desk's designated paper-mode job, in English, from the records it can read."""

    desk = roster.desk_for(code)
    facts = fx.desk_facts(db, code)
    status = _registry_status(facts)
    own = [fact for fact in fx.desk_only(facts) if fact.available]
    registry = [fact for fact in facts if fact.scope == "registry" and fact.available]
    shown = registry[:1] + own[: 1 if brief else 3]
    assigned = tasks.list_for(db, code)
    untrusted = [fact for fact in own if fact.untrusted]
    lines = [
        f"{desk.name}, {desk.role}. {_availability(status)} {JOB[desk.code]}",
        _task_sentence(assigned),
        _activity(db, code),
    ]
    lines.extend(fact.text for fact in untrusted)
    if code == roster.SUPERVISOR and not brief:
        lines.append(_floor_summary(db))
    if not shown:
        lines.append("I read my desk and found no stored records. I will not invent any.")
    lines.append(NO_ORDER)
    content = safety.clean(" ".join(lines), 3900)
    cited = list(shown)
    cited.extend(fact for fact in untrusted if fact not in cited)
    made = Report(content, [fact.citation() for fact in cited], status=status)
    registry_fact = next((fact for fact in facts if fact.key == "registry"), None)
    made.meta["diagnostics"] = {
        "registry_status": status,
        "paper_only": True,
        "can_submit_orders": False,
        "can_sign": False,
        "can_transfer_funds": False,
        "holds_credentials": False,
        "assigned_tasks": [row.subject for row in assigned[:5]],
        "records": [fact.text for fact in shown],
        "registry_record": registry_fact.text if registry_fact is not None else None,
    }
    return made


def _floor_summary(db: Session) -> str:
    bits: list[str] = []
    for code in roster.CODES:
        if code == roster.SUPERVISOR:
            continue
        desk = roster.desk_for(code)
        assigned = tasks.list_for(db, code)
        if assigned:
            bits.append(f"{desk.name}: assigned {assigned[0].subject}")
        else:
            bits.append(f"{desk.name}: no assigned task")
    return "Floor: " + " ".join(bits)


def _digest(db: Session) -> str:
    parts: list[str] = []
    for code in roster.CODES:
        facts = fx.desk_facts(db, code)
        parts.append(_registry_status(facts))
        parts.extend(
            fact.text for fact in fx.desk_only(facts) if fact.available and fact.key != "runs"
        )
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()[:32]


def _floor_conversation(db: Session) -> ConversationRow:
    existing = db.scalars(
        select(ConversationRow)
        .where(
            ConversationRow.kind == "group",
            ConversationRow.title == FLOOR_TITLE,
            ConversationRow.status != "archived",
        )
        .limit(1)
    ).first()
    if existing is not None:
        return existing
    return store.create_conversation(
        db,
        kind="group",
        title=FLOOR_TITLE,
        topic="Each desk reports its designated paper-mode task in English.",
        agents=list(roster.CODES),
        created_by="system",
        max_messages=500,
        moderator=roster.SUPERVISOR,
    )


def _record_runs(db: Session, digest: str, correlation_id: str) -> None:
    now = datetime.now(UTC)
    for desk in roster.DESKS:
        agent = db.scalars(select(AgentRow).where(AgentRow.code == desk.code)).first()
        if agent is None:
            continue
        key = f"floor-{desk.code}-{digest}"
        already = db.scalars(
            select(AgentRunRow).where(AgentRunRow.idempotency_key == key).limit(1)
        ).first()
        if already is not None:
            continue
        db.add(
            AgentRunRow(
                id=uuid.uuid4(),
                agent_id=agent.id,
                idempotency_key=key,
                correlation_id=correlation_id[:64],
                status="recorded",
                started_at=now,
                finished_at=now,
                created_at=now,
                summary=(
                    f"{desk.name} read local records for the {desk.role}. "
                    f"{desk.summary} Paper only. No order submitted."
                )[:500],
            )
        )
    db.flush()


def record_floor(db: Session, correlation_id: str) -> tuple[list[MessageRow], bool]:
    """Store one English report per desk. A repeat with the same records is not a new report.

    Returns `(rows, created)`.
    """

    conv = _floor_conversation(db)
    digest = _digest(db)
    recent = list(
        db.scalars(
            select(MessageRow)
            .where(MessageRow.conversation_id == conv.id)
            .order_by(MessageRow.seq.desc())
            .limit(40)
        )
    )
    matched = [row for row in recent if str((row.meta or {}).get("floor_digest") or "") == digest]
    if len(matched) >= len(roster.CODES):
        matched.sort(key=lambda row: row.seq)
        return matched, False
    if store.message_count(db, conv.id) + len(roster.CODES) > conv.max_messages:
        raise store.StoreError("The floor conversation is full. No order was sent.")
    _record_runs(db, digest, correlation_id)
    posted: list[MessageRow] = []
    for code in roster.CODES:
        made = report(db, code)
        made.meta["floor_digest"] = digest
        posted.append(
            store.append_message(
                db,
                conv,
                sender_id=code,
                sender_kind="agent",
                content=made.content,
                kind="status",
                origin="tool_verified",
                correlation_id=correlation_id,
                recipients=[store.HUMAN],
                citations=made.citations,
                meta=made.meta,
                task_id=f"floor-{digest}",
            )
        )
    return posted, True
