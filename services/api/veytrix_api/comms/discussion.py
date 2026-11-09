"""Bounded desk-to-desk discussions and boardroom sessions.

No language model is configured, so every turn here is `simulated`: a fixed rule reads
each desk's own records and states how strong the evidence is. Turns say so, and the UI
shows the tag. The rules enforce what the spec asks for:

- a round limit, a message budget, and loop detection (a repeated message stops the run);
- a confirmation (`evidence`) must cite a trusted source the claim did not already cite, so
  one record cannot confirm itself and untrusted text never counts as a source;
- consensus is recorded only after an objection round, with no open objection, and with two
  or more distinct trusted sources. Otherwise the Supervisor says no consensus was recorded;
- dissent and unresolved questions are written out. Nothing here can place an order.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from veytrix_api.comms import facts as fx
from veytrix_api.comms import roster, safety, store
from veytrix_api.comms.envelope import Citation
from veytrix_api.models import ConversationRow, MessageRow

SUP = roster.SUPERVISOR
RISK = roster.RISK
NO_ACTION = (
    "No order, transfer, or live-mode change can follow from this discussion. "
    "It is an evidence review."
)
DEFAULT_AGENDA = (
    "Desk status and data gaps",
    "Risk limits and permissions",
    "Open questions for the owner",
)


class Stop(Exception):
    """Raised when the budget is spent or a loop is found. The run closes cleanly."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass
class Claim:
    code: str
    position: str
    message: MessageRow
    sources: set[str]
    untrusted_only: bool


@dataclass
class Run:
    db: Session
    conv: ConversationRow
    correlation_id: str
    task_id: str
    seen: set[str] = field(default_factory=set)
    posted: list[MessageRow] = field(default_factory=list)

    def say(
        self,
        code: str,
        content: str,
        kind: str,
        *,
        origin: str = "simulated",
        citations: list[Citation] | None = None,
        thread_id: uuid.UUID | None = None,
        meta: dict[str, object] | None = None,
        recipients: list[str] | None = None,
    ) -> MessageRow:
        if store.message_count(self.db, self.conv.id) >= self.conv.max_messages:
            raise Stop("budget_exhausted")
        key = hashlib.sha256(f"{code}|{safety.normalise(content)}".encode()).hexdigest()
        if key in self.seen:
            raise Stop("loop_detected")
        self.seen.add(key)
        row = store.append_message(
            self.db,
            self.conv,
            sender_id=code,
            sender_kind="agent",
            content=content,
            kind=kind,
            origin=origin,
            correlation_id=self.correlation_id,
            recipients=recipients or [],
            thread_id=thread_id,
            citations=citations,
            meta=meta,
            task_id=self.task_id,
            decision_id=f"dec-{self.task_id[-8:]}" if kind == "recommendation" else None,
        )
        self.posted.append(row)
        return row


def pick_participants(topic: str, requested: list[str] | None) -> list[str]:
    """Speaking desks. The Supervisor moderates and never appears here. Risk always speaks."""

    if requested:
        chosen = [c for c in dict.fromkeys(requested) if c in roster.BY_CODE and c != SUP]
    else:
        chosen = roster.relevant_desks(topic, limit=3, exclude=(SUP, RISK))
        if not chosen:
            chosen = ["RESEARCH-01", "TREASURY-01"]
    if RISK not in chosen:
        chosen.append(RISK)
    return chosen[:9]


def _trusted(items: list[fx.Fact]) -> list[fx.Fact]:
    return [f for f in items if f.available and f.has_data and not f.untrusted]


def position_for(code: str, topic: str, facts: list[fx.Fact]) -> str:
    """supported | thin | unavailable | abstain. About evidence strength, not about trading."""

    relevant = roster.relevant_desks(topic, limit=10)
    if relevant and code not in relevant and code != RISK:
        return "abstain"
    own = fx.desk_only(facts)
    if own and not any(f.available for f in own):
        return "unavailable"
    return "supported" if _trusted(own) else "thin"


def _brief(items: list[fx.Fact], limit: int = 2) -> str:
    chosen = [f for f in items if f.available][:limit] or items[:limit]
    return " ".join(f.text for f in chosen)


def _claim_text(desk: roster.Desk, topic: str, position: str, own: list[fx.Fact]) -> str:
    head = f"{desk.name} on “{safety.clean(topic, 90)}”. Evidence: {position}."
    if position == "abstain":
        return f"{head} This topic is outside my desk's records, so I abstain."
    if position == "unavailable":
        return f"{head} {_brief(own)} I cannot state a position."
    return f"{head} {_brief(own)}"


def _sources(items: list[fx.Fact]) -> set[str]:
    return {f"{f.source}:{f.ref}" for f in _trusted(items)}


def run_discussion(
    db: Session,
    conv: ConversationRow,
    *,
    topic: str,
    participants: list[str],
    rounds: int,
    correlation_id: str,
    task_id: str,
) -> list[MessageRow]:
    run = Run(db, conv, correlation_id, task_id)
    for row in store.recent(db, conv.id, 200):
        run.seen.add(
            hashlib.sha256(f"{row.sender_id}|{safety.normalise(row.content)}".encode()).hexdigest()
        )
    all_facts = {code: fx.desk_facts(db, code) for code in participants}
    claims: list[Claim] = []
    objections: list[tuple[Claim, MessageRow, Claim]] = []
    stopped: str | None = None
    rounds_run = 0
    try:
        run.say(
            SUP,
            f"Topic: “{safety.clean(topic, 160)}”. Format: thesis, evidence, objections, risk "
            f"assessment, recommendation, unresolved questions. Rounds: {rounds}. Budget: "
            f"{conv.max_messages} messages. I moderate and have no records of my own on this. "
            f"{NO_ACTION} These turns are rule-based and simulated: no model is configured.",
            "notice",
            origin="scripted",
            recipients=participants,
            citations=[Citation(source="roster", ref=SUP, label=roster.desk_for(SUP).summary)],
        )
        rounds_run = 1
        for code in participants:
            desk = roster.desk_for(code)
            own = fx.desk_only(all_facts[code])
            position = position_for(code, topic, all_facts[code])
            citations = [f.citation() for f in own if f.available] or [
                f.citation() for f in all_facts[code] if f.scope == "registry"
            ][:1]
            if code == RISK:
                limits = (
                    "Risk assessment. No action is proposed. If one were, these records set the "
                    "limits. " + _brief(own, 3)
                )
                row = run.say(
                    code,
                    f"{desk.name}: {limits} Evidence: {position}.",
                    "risk_assessment",
                    citations=citations,
                    meta={"position": position, "round": 1},
                )
            else:
                row = run.say(
                    code,
                    _claim_text(desk, topic, position, own),
                    "claim",
                    citations=citations,
                    meta={"position": position, "round": 1},
                )
            claims.append(
                Claim(
                    code,
                    position,
                    row,
                    _sources(own),
                    untrusted_only=not _trusted(own) and any(f.untrusted for f in own),
                )
            )

        if rounds >= 2:
            rounds_run = 2
            backed = [c for c in claims if c.position == "supported" and c.code != RISK]
            for index, objector in enumerate(claims):
                if objector.code == RISK or objector.position == "abstain":
                    continue
                targets = [t for t in backed if t.code != objector.code]
                if not targets:
                    continue
                target = targets[index % len(targets)]
                tdesk, odesk = roster.desk_for(target.code), roster.desk_for(objector.code)
                if len(target.sources) < 2:
                    text = (
                        f"{odesk.name} objects to {tdesk.name}'s claim. It rests on "
                        f"{len(target.sources)} trusted source(s). One record cannot confirm "
                        "itself, so I do not count it as a confirmation."
                    )
                    row = run.say(
                        objector.code,
                        text,
                        "objection",
                        citations=[Citation(**c) for c in target.message.citations],
                        thread_id=target.message.id,
                        meta={"position": "objection", "target": target.code, "round": 2},
                    )
                    objections.append((objector, row, target))
                    continue
                own = fx.desk_only(all_facts[objector.code])
                independent = [
                    f for f in _trusted(own) if f"{f.source}:{f.ref}" not in target.sources
                ]
                if independent:
                    run.say(
                        objector.code,
                        f"{odesk.name} checks {tdesk.name}'s claim from my own records. "
                        + _brief(independent),
                        "evidence",
                        citations=[f.citation() for f in independent[:3]],
                        thread_id=target.message.id,
                        meta={"position": "independent_check", "target": target.code, "round": 2},
                    )
                else:
                    run.say(
                        objector.code,
                        f"{odesk.name} has no independent record to check {tdesk.name}'s claim. "
                        "Which source outside both desks covers it?",
                        "question",
                        citations=[],
                        thread_id=target.message.id,
                        meta={
                            "position": "no_independent_source",
                            "target": target.code,
                            "round": 2,
                        },
                    )

        resolved: set[uuid.UUID] = set()
        if rounds >= 3 and objections:
            rounds_run = 3
            for _objector, objection, target in objections:
                own = fx.desk_only(all_facts[target.code])
                extra = [f for f in _trusted(own) if f"{f.source}:{f.ref}" not in target.sources]
                tdesk = roster.desk_for(target.code)
                if extra:
                    run.say(
                        target.code,
                        f"{tdesk.name} answers with a further record. " + _brief(extra),
                        "evidence",
                        citations=[f.citation() for f in extra[:3]],
                        thread_id=objection.id,
                        meta={"position": "answers_objection", "round": 3},
                    )
                    resolved.add(objection.id)
                else:
                    run.say(
                        target.code,
                        f"{tdesk.name} has no further independent record. "
                        "The objection stays open.",
                        "status",
                        citations=[],
                        thread_id=objection.id,
                        meta={"position": "objection_open", "round": 3},
                    )
    except Stop as stop:
        stopped = stop.reason
        store.record_event(
            db,
            conv.id,
            stop.reason,
            actor=SUP,
            correlation_id=correlation_id,
            payload={"rounds_run": rounds_run},
        )
        resolved = set()

    _close_out(
        run, topic, participants, claims, objections, resolved, rounds_run, stopped, all_facts
    )
    return run.posted


def _close_out(
    run: Run,
    topic: str,
    participants: list[str],
    claims: list[Claim],
    objections: list[tuple[Claim, MessageRow, Claim]],
    resolved: set[uuid.UUID],
    rounds_run: int,
    stopped: str | None,
    all_facts: dict[str, list[fx.Fact]],
) -> None:
    tally: dict[str, int] = {}
    for claim in claims:
        tally[claim.position] = tally.get(claim.position, 0) + 1
    open_objections = [o for o in objections if o[1].id not in resolved]
    supported_sources: set[str] = set()
    for claim in claims:
        if claim.position == "supported":
            supported_sources |= claim.sources
    if stopped:
        verdict = f"No consensus recorded: the run stopped early ({stopped.replace('_', ' ')})."
    elif rounds_run < 2:
        verdict = "No consensus recorded: no objection round was held."
    elif open_objections:
        verdict = f"No consensus recorded: {len(open_objections)} objection(s) remain open."
    elif len(supported_sources) < 2:
        verdict = "No consensus recorded: fewer than two distinct trusted sources back the claims."
    else:
        verdict = (
            f"Consensus recorded on the evidence only, across {len(supported_sources)} distinct "
            "trusted sources. It is not a trade decision."
        )
    thin = [c for c in claims if c.position in ("thin", "unavailable")]
    abstain = [c for c in claims if c.position == "abstain"]
    parts = [
        f"Recommendation on “{safety.clean(topic, 100)}”. Evidence by desk: "
        + ", ".join(f"{count} {name}" for name, count in sorted(tally.items()))
        + ".",
        verdict,
        "Dissent: "
        + (
            "; ".join(
                f"{roster.name_of(o[0].code)} against {roster.name_of(o[2].code)}"
                for o in open_objections
            )
            if open_objections
            else "no open objection."
        ),
        "Unresolved: "
        + (
            "; ".join(f"{roster.name_of(c.code)} has {c.position} evidence" for c in thin)
            if thin
            else "none recorded."
        ),
        NO_ACTION,
    ]
    cites = [
        Citation(
            source="messages",
            ref=str(run.conv.id),
            label=f"{len(run.posted)} persisted messages in this discussion",
        )
    ]
    try:
        run.say(
            SUP,
            "\n".join(parts),
            "recommendation",
            citations=cites,
            meta={
                "consensus": verdict.startswith("Consensus"),
                "rounds_run": rounds_run,
                "open_objections": len(open_objections),
                "abstained": len(abstain),
            },
        )
        for claim in thin[:3]:
            desk = roster.desk_for(claim.code)
            run.say(
                SUP,
                f"Proposed owner: {desk.name}. Add records for “{safety.clean(topic, 80)}” "
                f"(evidence is {claim.position}). Status: proposed. Nothing was started and no "
                "order is involved.",
                "assignment",
                citations=[],
                recipients=[claim.code],
                meta={"tool_status": "proposed", "owner": claim.code},
            )
    except Stop as stop:
        store.record_event(
            run.db,
            run.conv.id,
            stop.reason,
            actor=SUP,
            correlation_id=run.correlation_id,
            payload={"phase": "closing"},
        )
    run.conv.status = "closed"
    run.conv.closed_at = datetime.now(UTC)
    store.add_summary(
        run.db, run.conv.id, store.last_seq(run.db, run.conv.id), "\n".join(parts), "simulated"
    )
    store.record_event(
        run.db,
        run.conv.id,
        "discussion_closed",
        actor=SUP,
        correlation_id=run.correlation_id,
        payload={"rounds_run": rounds_run, "tally": tally, "participants": participants},
    )


def run_boardroom(
    db: Session,
    conv: ConversationRow,
    *,
    agenda: list[str],
    correlation_id: str,
    task_id: str,
) -> list[MessageRow]:
    run = Run(db, conv, correlation_id, task_id)
    speakers = [c for c in roster.CODES if c != SUP]
    all_facts = {code: fx.desk_facts(db, code) for code in speakers}
    votes: dict[str, int] = {}
    stopped: str | None = None
    wednesday = datetime.now(UTC).weekday() == 2
    try:
        run.say(
            SUP,
            "Boardroom session opened"
            + ("." if wednesday else " off schedule: the regular session is Wednesday.")
            + f" Agenda: {'; '.join(agenda)}. Each desk speaks once per item from its own "
            f"records. Positions are rule-based and simulated: no model is configured. {NO_ACTION}",
            "notice",
            origin="scripted",
            recipients=speakers,
            meta={"scheduled": wednesday},
        )
        for number, item in enumerate(agenda, start=1):
            run.say(
                SUP,
                f"Agenda item {number}: {safety.clean(item, 120)}.",
                "notice",
                origin="scripted",
                meta={"agenda_item": number},
            )
            item_tally: dict[str, int] = {}
            for code in speakers:
                desk = roster.desk_for(code)
                own = fx.desk_only(all_facts[code])
                position = position_for(code, item, all_facts[code])
                item_tally[position] = item_tally.get(position, 0) + 1
                votes[position] = votes.get(position, 0) + 1
                run.say(
                    code,
                    _claim_text(desk, item, position, own),
                    "status",
                    citations=[f.citation() for f in own if f.available][:3],
                    meta={"position": position, "agenda_item": number},
                )
            run.say(
                SUP,
                f"Item {number} recorded. Evidence by desk: "
                + ", ".join(f"{n} {k}" for k, n in sorted(item_tally.items()))
                + ". This is a tally of evidence, not a vote to trade.",
                "recommendation",
                citations=[
                    Citation(
                        source="messages",
                        ref=str(conv.id),
                        label="Positions stated in this session",
                    )
                ],
                meta={"agenda_item": number, "tally": item_tally},
            )
    except Stop as stop:
        stopped = stop.reason
        store.record_event(
            db,
            conv.id,
            stop.reason,
            actor=SUP,
            correlation_id=correlation_id,
            payload={"phase": "boardroom"},
        )
    minutes = (
        f"Minutes: {len(run.posted)} messages, {len(agenda)} agenda item(s). Totals across items: "
        + (", ".join(f"{n} {k}" for k, n in sorted(votes.items())) or "none")
        + (f". Stopped early: {stopped.replace('_', ' ')}." if stopped else ".")
        + f" {NO_ACTION}"
    )
    try:
        run.say(
            SUP,
            minutes,
            "summary",
            origin="tool_verified",
            citations=[
                Citation(source="messages", ref=str(conv.id), label="Count of persisted messages")
            ],
        )
        owners = [
            c
            for c in speakers
            if position_for(c, " ".join(agenda), all_facts[c]) in ("thin", "unavailable")
        ][:3]
        for code in owners:
            run.say(
                SUP,
                f"Proposed owner: {roster.name_of(code)}. Close the data gap on this "
                "desk. Status: proposed. Nothing was started.",
                "assignment",
                recipients=[code],
                meta={"tool_status": "proposed", "owner": code},
            )
    except Stop:
        pass
    conv.status = "closed"
    conv.closed_at = datetime.now(UTC)
    store.add_summary(db, conv.id, store.last_seq(db, conv.id), minutes, "tool_verified")
    store.record_event(
        db,
        conv.id,
        "boardroom_closed",
        actor=SUP,
        correlation_id=correlation_id,
        payload={"agenda": agenda, "totals": votes},
    )
    return run.posted
