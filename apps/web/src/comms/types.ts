import type { AgentCode } from "../api/types";

export type Origin = "human" | "scripted" | "model_generated" | "tool_verified" | "simulated";
export type SenderKind = "human" | "agent" | "system" | "tool";
export type ConversationKind = "direct" | "group" | "discussion" | "boardroom";
export type ConversationStatus = "open" | "paused" | "closed" | "archived";

export type Citation = {
  source: string;
  ref: string;
  label: string;
  as_of: string | null;
  untrusted: boolean;
};

export type CommsMessage = {
  message_id: string;
  conversation_id: string;
  seq: number;
  thread_id: string | null;
  sender_id: string;
  sender_name: string;
  sender_kind: SenderKind;
  recipient_ids: string[];
  kind: string;
  origin: Origin;
  origin_label: string;
  timestamp: string;
  correlation_id: string;
  task_id: string | null;
  decision_id: string | null;
  tool_call_id: string | null;
  content: string;
  status: "delivered" | "failed" | "cancelled";
  visibility: "conversation" | "private";
  citations: Citation[];
  meta: Record<string, unknown>;
};

export type Member = {
  member_id: string;
  member_name: string;
  member_kind: "human" | "agent";
  role: string;
  last_read_seq: number;
};

export type Conversation = {
  conversation_id: string;
  kind: ConversationKind;
  title: string;
  topic: string;
  status: ConversationStatus;
  pinned: boolean;
  created_by: "human" | "system";
  owner_id: string | null;
  max_rounds: number;
  max_messages: number;
  created_at: string;
  updated_at: string;
  closed_at: string | null;
  message_count: number;
  unread: number;
  members: Member[];
  agenda: string[] | null;
  last_message: CommsMessage | null;
};

export type Flags = {
  flags: Record<string, boolean>;
  realtime: "not_configured" | "configured";
  model: "not_configured";
  language: "en";
  note: string;
};

export type SendResult = {
  conversation: Conversation;
  messages: CommsMessage[];
  duplicate: boolean;
  held: string | null;
  errors: string[];
  realtime: "not_configured" | "published" | "failed";
};

export type Speech = {
  id: string;
  code: AgentCode;
  text: string;
  origin: Origin;
  label: string;
  conversationId: string;
  conversationKind: ConversationKind | "unknown";
  participants: AgentCode[];
  replay: boolean;
  peerReply: boolean;
  /** Changes every time this line is shown, so the bubble animation restarts. */
  token?: number;
};

/** Short tag shown next to a bubble or a message. Honest about where the words came from. */
export const ORIGIN_TAG: Record<Origin, string> = {
  human: "you",
  scripted: "scripted",
  model_generated: "model",
  tool_verified: "verified",
  simulated: "simulated",
};
