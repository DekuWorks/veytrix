"""Compose a desk's reply to the user from verified local records.

No language model is configured in this build, so a reply is never `model_generated`.
It is `tool_verified` when every claim comes from a read of local records, and `scripted`
when it is fixed text (a glossary entry, a refusal with no registry row, a clarifying
question). The intent is chosen by plain patterns. Chat text cannot reach anything that
places an order: this module only reads.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from veytrix_api.comms import facts as fx
from veytrix_api.comms import glossary, roster, safety
from veytrix_api.comms.envelope import Citation, Level, MessageKind, Origin
from veytrix_api.models import MessageRow

MAX_CONTENT = 3900

_ACTIONS = re.compile(
    r"(what|which|any|show).{0,40}(actions?|orders?|trades?|fills?)"
    r".{0,40}(executed|placed|sent|submitted|filled|done|happened|actually)"
    r"|actually (executed|placed|sent|done)|did (you|anyone|the bot|mac-?01).{0,30}"
    r"(order|trade|buy|sell|execute|place)|what did you (do|execute|place)",
    re.IGNORECASE,
)
_SOURCES = re.compile(
    r"\bsources?\b|where did you (get|read|see)|\bcite\b|citations?|evidence", re.I
)
_DISAGREE = re.compile(
    r"disagree|push(ed)? back|objection|dissent|why did you (object|oppose)", re.I
)
_WORKING = re.compile(
    r"what('?s| is| are) you.{0,15}(working|doing|up to|on)|working on|your status"
    r"|what('?s| is) (going on|happening)",
    re.I,
)
_DEFINE_CUE = re.compile(
    r"what('?s| is| are| does)|define|meaning|explain|teach|tell me about|how does|\bmean\b|\?",
    re.I,
)
_EXPLAIN = re.compile(
    r"^\s*(explain( this| that| it)?|why( is that| so)?|how come|how did you.*)\s*\??\s*$", re.I
)
_HELLO = re.compile(r"^\s*(hi|hello|hey|yo|good (morning|afternoon|evening))\b", re.I)
_HELP = re.compile(r"\b(help|what can you do|capabilities|commands)\b", re.I)
_DATA = re.compile(
    r"\b(data|latest|current|numbers?|show|read|see|how many|count|summary|summarise|summarize|"
    r"report|overview|tell me)\b",
    re.I,
)


@dataclass(frozen=True)
class Reply:
    content: str
    kind: MessageKind
    origin: Origin
    citations: list[Citation] = field(default_factory=list)
    meta: dict[str, object] = field(default_factory=dict)


def _cut(text: str) -> str:
    return text if len(text) <= MAX_CONTENT else text[: MAX_CONTENT - 1].rstrip() + "…"


def _numbered(items: list[fx.Fact], start: int = 1) -> tuple[str, list[Citation]]:
    lines: list[str] = []
    cites: list[Citation] = []
    for index, fact in enumerate(items, start=start):
        lines.append(f"- {fact.text} [{index}]")
        cites.append(fact.citation())
    return "\n".join(lines), cites


def classify(text: str) -> str:
    """Name the intent. Order matters: a question about past actions is not an order."""

    if _ACTIONS.search(text):
        return "actions"
    if _SOURCES.search(text):
        return "sources"
    if _DISAGREE.search(text):
        return "disagree"
    if safety.wants_order(text):
        return "refusal"
    if _WORKING.search(text):
        return "working_on"
    term = glossary.find(text)
    if term is not None and (_DEFINE_CUE.search(text) or len(text.split()) <= 3):
        return "define"
    if _EXPLAIN.match(text):
        return "explain"
    if _HELLO.match(text):
        return "greeting"
    if _HELP.search(text):
        return "help"
    if _DATA.search(text):
        return "desk_data"
    return "unclear"


def _mine(history: list[MessageRow], code: str) -> MessageRow | None:
    for row in history:
        if row.sender_id == code and row.sender_kind == "agent":
            return row
    return None


def compose_reply(
    db: Session,
    code: str,
    text: str,
    *,
    history: list[MessageRow],
    level: Level | None = None,
    brief: bool = False,
) -> Reply:
    """`history` is newest first. `brief` keeps a group reply to a couple of lines."""

    from veytrix_api.comms import store  # local import: store does not import replies

    desk = roster.desk_for(code)
    intent = classify(text)
    meta: dict[str, object] = {"intent": intent}

    if intent == "greeting" or intent == "help":
        from veytrix_api.claude_provider import probe, speak

        status = probe()
        if not status.connected:
            content = (
                f"{desk.name} cannot answer with a model. Claude is offline. "
                "This line is not a model reply. "
                "Ask “What are you working on?” for a line labelled from local records. "
                "No order is sent."
            )
            meta["model"] = "disconnected"
            meta["language"] = "en"
            return Reply(
                _cut(content),
                "reply",
                "scripted",
                [Citation(source="roster", ref=code, label=desk.summary)],
                meta,
            )
        spoken = speak(code)
        meta["model"] = spoken.claude
        meta["language"] = "en"
        return Reply(
            _cut(spoken.text),
            "reply",
            spoken.origin,
            [Citation(source="roster", ref=code, label=desk.summary)],
            meta,
        )

    if intent == "define":
        term = glossary.find(text)
        assert term is not None
        chosen = level or glossary.level_from(text)
        meta["level"] = chosen
        content = (
            f"{term.title} ({chosen}): {term.at(chosen)}\n"
            "Ask for “beginner”, “intermediate”, or “advanced” to change the level. "
            "This is fixed teaching text, not advice."
        )
        return Reply(
            _cut(content),
            "reply",
            "scripted",
            [Citation(source="glossary", ref=term.key, label=term.title)],
            meta,
        )

    if intent == "sources":
        last = _mine(history, code)
        if last is None or not last.citations:
            return Reply(
                "I have not made a statement with sources in this conversation yet. Ask what I am "
                "working on and I will cite the records I read.",
                "reply",
                "scripted",
                [],
                meta,
            )
        lines = []
        for index, cite in enumerate(last.citations, start=1):
            stamp = f", as of {cite['as_of']}" if cite.get("as_of") else ""
            flag = " (untrusted text)" if cite.get("untrusted") else ""
            lines.append(
                f"{index}. {cite['label']} ({cite['source']} / {cite['ref']}{stamp}){flag}"
            )
        content = f"Sources for my message #{last.seq} ({last.origin}):\n" + "\n".join(lines)
        return Reply(
            _cut(content),
            "reply",
            "tool_verified",
            [Citation(**c) for c in last.citations],
            {**meta, "about_seq": last.seq},
        )

    if intent == "explain":
        last = _mine(history, code)
        if last is None:
            return Reply(
                "Explain what? I have not said anything here yet. Ask me something first, or name "
                "a term and I will define it.",
                "clarification",
                "scripted",
                [],
                meta,
            )
        content = (
            f"My message #{last.seq} was a {last.kind} with origin “{last.origin}”. It rests on "
            f"{len(last.citations)} record(s) listed under its sources. I add no outside "
            "information and no model reasoning. Ask “Show sources” for the records."
        )
        return Reply(
            _cut(content),
            "reply",
            "tool_verified",
            [Citation(**c) for c in last.citations],
            {**meta, "about_seq": last.seq},
        )

    if intent == "disagree":
        found = store.latest_objection(db, code)
        if found is None:
            return Reply(
                f"I have not recorded an objection in any discussion. {desk.name} has nothing to "
                "explain yet. You can start a discussion from the Conversations panel.",
                "reply",
                "scripted",
                [],
                meta,
            )
        message, title = found
        content = (
            f"In “{title}” (message #{message.seq}) I objected:\n{message.content}\n"
            f"That message was {message.origin}. If it says simulated, the stance came from a "
            "fixed rule over my records, not from a model."
        )
        return Reply(
            _cut(content),
            "reply",
            "tool_verified",
            [Citation(**c) for c in message.citations],
            {**meta, "about_seq": message.seq},
        )

    registry = fx.registry_facts(db, code)
    registry_ok = any(f.available for f in registry)

    if intent == "refusal":
        denied = next((f for f in registry if f.key == "permissions"), None)
        status = next((f for f in registry if f.key == "registry"), None)
        content = (
            f"{desk.name}: I can't do that, and chat can't make me. "
            + (status.text + " " if status else "")
            + (denied.text + " " if denied else "")
            + "No route in this build submits an order or moves funds. I can read my records "
            "instead: ask “What are you working on?”."
        )
        return Reply(
            _cut(content),
            "refusal",
            "tool_verified" if registry_ok else "scripted",
            [f.citation() for f in registry if f.available],
            meta,
        )

    if intent == "actions":
        executed = fx.execution_facts(db)
        body, cites = _numbered(
            [f for f in executed if f.available] + [f for f in executed if not f.available]
        )
        own = next((f for f in registry if f.key == "registry"), None)
        content = (
            "What was actually executed, from the ledger:\n"
            + body
            + (f"\n{desk.name} itself executed nothing. {own.text}" if own else "")
        )
        return Reply(
            _cut(content),
            "reply",
            "tool_verified",
            cites,
            {
                **meta,
                "tool_status_vocabulary": "filled needs a broker order id and filled quantity",
            },
        )

    # Domain questions: redirect if another desk is a clearly better reader.
    better = roster.relevant_desks(text, limit=1)
    own_rank = roster.relevant_desks(text, limit=10)
    if (
        intent in ("desk_data", "unclear")
        and better
        and better[0] != code
        and code not in own_rank
        and code != roster.SUPERVISOR
    ):
        other = roster.desk_for(better[0])
        return Reply(
            f"That is {other.name}'s desk ({other.role}). I can't read it. "
            f"Open {other.name}'s chat "
            f"or write @{other.name} in a group room.",
            "clarification",
            "scripted",
            [Citation(source="roster", ref=other.code, label=other.summary)],
            {**meta, "redirect": other.code},
        )

    all_facts = fx.desk_facts(db, code)
    desk_scoped = fx.desk_only(all_facts)

    if intent == "working_on":
        runs = next((f for f in registry if f.key == "runs"), None)
        status = next((f for f in registry if f.key == "registry"), None)
        shown = ([status] if status else []) + ([runs] if runs else [])
        if not brief:
            shown += desk_scoped
        body, cites = _numbered(shown)
        head = f"{desk.name}, {desk.role}. Nothing is running on this desk: it has no worker."
        content = f"{head}\n{body}" + (
            "" if brief else "\nAsk “Show sources” for the records behind this."
        )
        return Reply(
            _cut(content), "reply", "tool_verified" if registry_ok else "scripted", cites, meta
        )

    if intent == "desk_data":
        body, cites = _numbered(desk_scoped or all_facts)
        content = f"From my desk records:\n{body}"
        return Reply(_cut(content), "reply", "tool_verified", cites, meta)

    content = (
        f"I am not sure what you want {desk.name} to look at. I can read: {desk.summary} "
        "Which of those do you mean? You can also ask “What are you working on?” or "
        "“What is a stop loss?”."
    )
    return Reply(
        _cut(content),
        "clarification",
        "scripted",
        [Citation(source="roster", ref=code, label=desk.summary)],
        meta,
    )
