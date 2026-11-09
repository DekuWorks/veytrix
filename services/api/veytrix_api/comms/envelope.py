"""Typed message envelope and request bodies for the communication routes.

Every response says `execution_permitted` and `order_submitted` are false. No
field in this module can carry an order, a key, or a broker instruction.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SenderKind = Literal["human", "agent", "system", "tool"]
Origin = Literal["human", "scripted", "model_generated", "tool_verified", "simulated"]
MessageKind = Literal[
    "chat",
    "reply",
    "question",
    "clarification",
    "claim",
    "objection",
    "evidence",
    "risk_assessment",
    "recommendation",
    "summary",
    "status",
    "notice",
    "assignment",
    "refusal",
]
ConversationKind = Literal["direct", "group", "discussion", "boardroom"]
ConversationStatus = Literal["open", "paused", "closed", "archived"]
MessageStatus = Literal["delivered", "failed", "cancelled"]
Visibility = Literal["conversation", "private"]
Level = Literal["beginner", "intermediate", "advanced"]

# Phase 6 vocabulary. A status is only `filled` when a broker-confirmed row says so.
ToolStatus = Literal[
    "researching",
    "proposed",
    "awaiting_approval",
    "submitted",
    "filled",
    "partially_filled",
    "rejected",
    "failed",
    "cancelled",
    "unknown",
]

ORIGIN_LABELS: dict[str, str] = {
    "human": "you",
    "scripted": "scripted",
    "model_generated": "model",
    "tool_verified": "verified from local records",
    "simulated": "simulated (rule-based, no model)",
}

_CLIENT_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class Citation(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: str = Field(max_length=48)
    ref: str = Field(max_length=96)
    label: str = Field(max_length=200)
    as_of: str | None = None
    untrusted: bool = False


class MessageOut(BaseModel):
    message_id: uuid.UUID
    conversation_id: uuid.UUID
    seq: int
    thread_id: uuid.UUID | None
    sender_id: str
    sender_name: str
    sender_kind: SenderKind
    recipient_ids: list[str]
    kind: MessageKind
    origin: Origin
    origin_label: str
    timestamp: datetime
    correlation_id: str
    task_id: str | None
    decision_id: str | None
    tool_call_id: str | None
    content: str
    status: MessageStatus
    visibility: Visibility
    citations: list[Citation]
    meta: dict[str, object]


class MemberOut(BaseModel):
    member_id: str
    member_name: str
    member_kind: Literal["human", "agent"]
    role: str
    last_read_seq: int


class ConversationOut(BaseModel):
    conversation_id: uuid.UUID
    kind: ConversationKind
    title: str
    topic: str
    status: ConversationStatus
    pinned: bool
    created_by: Literal["human", "system"]
    owner_id: str | None
    max_rounds: int
    max_messages: int
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None
    message_count: int
    unread: int
    members: list[MemberOut]
    agenda: list[str] | None = None
    last_message: MessageOut | None = None


class Safety(BaseModel):
    execution_permitted: Literal[False] = False
    order_submitted: Literal[False] = False
    live_execution: Literal[False] = False


class ConversationEnvelope(Safety):
    conversation: ConversationOut


class ConversationListResponse(Safety):
    conversations: list[ConversationOut]
    source: Literal["local_database"] = "local_database"


class MessageListResponse(Safety):
    conversation_id: uuid.UUID
    messages: list[MessageOut]
    has_more: bool
    next_after_seq: int


class SendResult(Safety):
    conversation: ConversationOut
    messages: list[MessageOut]
    duplicate: bool = False
    held: str | None = None
    errors: list[str] = Field(default_factory=list)
    realtime: Literal["not_configured", "published", "failed"] = "not_configured"


class FeedResponse(Safety):
    messages: list[MessageOut]
    realtime: Literal["not_configured", "configured"]


class FlagsResponse(Safety):
    flags: dict[str, bool]
    realtime: Literal["not_configured", "configured"]
    model: Literal["not_configured"] = "not_configured"
    note: str


class RosterEntry(BaseModel):
    code: str
    registry_id: str
    name: str
    role: str
    desk: str
    summary: str
    tools_denied: int
    presence: str


class RosterResponse(Safety):
    desks: list[RosterEntry]
    source: Literal["local_roster"] = "local_roster"


class CreateConversation(BaseModel):
    kind: ConversationKind
    agent_code: str | None = Field(default=None, max_length=32)
    participants: list[str] | None = Field(default=None, max_length=10)
    title: str | None = Field(default=None, max_length=120)

    @field_validator("title")
    @classmethod
    def _title(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class SendMessage(BaseModel):
    content: str = Field(min_length=1, max_length=1000)
    client_message_id: str | None = Field(default=None, max_length=64)
    thread_id: uuid.UUID | None = None
    level: Level | None = None

    @field_validator("content")
    @classmethod
    def _content(cls, value: str) -> str:
        text = "".join(ch for ch in value if ch == "\n" or ch >= " ").strip()
        if not text:
            raise ValueError("Message is empty.")
        return text

    @field_validator("client_message_id")
    @classmethod
    def _client_id(cls, value: str | None) -> str | None:
        if value is not None and not _CLIENT_ID.fullmatch(value):
            raise ValueError("client_message_id must be 1 to 64 letters, digits, - or _.")
        return value


class StartDiscussion(BaseModel):
    topic: str = Field(min_length=3, max_length=200)
    participants: list[str] | None = Field(default=None, max_length=10)
    rounds: int = Field(default=2, ge=1, le=3)
    kind: Literal["discussion", "boardroom"] = "discussion"
    agenda: list[str] | None = Field(default=None, max_length=3)

    @field_validator("topic")
    @classmethod
    def _topic(cls, value: str) -> str:
        text = " ".join("".join(ch for ch in value if ch >= " ").split())
        if len(text) < 3:
            raise ValueError("Topic is too short.")
        return text


class Moderate(BaseModel):
    action: Literal["close", "pause", "resume", "redirect", "assign_owner", "request_evidence"]
    agent_code: str | None = Field(default=None, max_length=32)
    note: str | None = Field(default=None, max_length=200)


class PatchConversation(BaseModel):
    pinned: bool | None = None
    archived: bool | None = None
    title: str | None = Field(default=None, min_length=1, max_length=120)


class ReadMark(BaseModel):
    seq: int = Field(ge=0)


class TriggerBody(BaseModel):
    task: Literal["reconcile", "risk_check", "position_size", "sma_crossover", "treasury_split"]
