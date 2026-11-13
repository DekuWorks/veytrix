import { apiGet, apiPatch, apiPost } from "../api/client";
import type { AgentCode } from "../api/types";
import type {
  CommsMessage,
  Conversation,
  Flags,
  SendResult,
} from "./types";

const BASE = "/api/v1/comms";

type MessagePage = {
  conversation_id: string;
  messages: CommsMessage[];
  has_more: boolean;
  next_after_seq: number;
};

export function getFlags(): Promise<Flags> {
  return apiGet<Flags>(`${BASE}/flags`);
}

export async function listConversations(query?: string, archived = false): Promise<Conversation[]> {
  const params = new URLSearchParams();
  if (query) {
    params.set("q", query);
  }
  if (archived) {
    params.set("archived", "true");
  }
  const suffix = params.size > 0 ? `?${params.toString()}` : "";
  const body = await apiGet<{ conversations: Conversation[] }>(`${BASE}/conversations${suffix}`);
  return body.conversations;
}

export async function openDirect(code: AgentCode): Promise<Conversation> {
  const body = await apiPost<{ conversation: Conversation }>(`${BASE}/conversations`, {
    kind: "direct",
    agent_code: code,
  });
  return body.conversation;
}

export async function openAllHands(): Promise<Conversation> {
  const body = await apiPost<{ conversation: Conversation }>(`${BASE}/conversations`, {
    kind: "group",
  });
  return body.conversation;
}

export async function loadMessages(conversationId: string): Promise<CommsMessage[]> {
  const out: CommsMessage[] = [];
  let after = 0;
  for (let page = 0; page < 20; page += 1) {
    const body = await apiGet<MessagePage>(
      `${BASE}/conversations/${conversationId}/messages?after_seq=${after}&limit=100`,
    );
    out.push(...body.messages);
    if (!body.has_more) {
      break;
    }
    after = body.next_after_seq;
  }
  return out;
}

export function sendMessage(conversationId: string, content: string): Promise<SendResult> {
  return apiPost<SendResult>(`${BASE}/conversations/${conversationId}/messages`, {
    content,
    client_message_id: crypto.randomUUID().replace(/-/g, "").slice(0, 32),
  });
}

export function startDiscussion(
  topic: string,
  rounds: number,
  kind: "discussion" | "boardroom" = "discussion",
): Promise<SendResult> {
  return apiPost<SendResult>(`${BASE}/discussions`, { topic, rounds, kind });
}

export function moderate(
  conversationId: string,
  action: "close" | "pause" | "resume",
): Promise<SendResult> {
  return apiPost<SendResult>(`${BASE}/conversations/${conversationId}/moderate`, { action });
}

export async function patchConversation(
  conversationId: string,
  patch: { pinned?: boolean; archived?: boolean },
): Promise<Conversation> {
  const body = await apiPatch<{ conversation: Conversation }>(
    `${BASE}/conversations/${conversationId}`,
    patch,
  );
  return body.conversation;
}

/** Ask another desk to answer one stored line. The server stores at most one reply. */
export function answerMessage(messageId: string): Promise<SendResult> {
  return apiPost<SendResult>(`${BASE}/messages/${messageId}/answer`, {});
}

/** Each desk writes its current paper-mode job in English. A repeat is the same report. */
export function startFloor(): Promise<SendResult> {
  return apiPost<SendResult>(`${BASE}/floor`, {});
}

export function markRead(conversationId: string, seq: number): Promise<unknown> {
  return apiPost(`${BASE}/conversations/${conversationId}/read`, { seq });
}

export async function loadFeed(): Promise<{
  messages: CommsMessage[];
  realtime: "not_configured" | "configured";
}> {
  return apiGet(`${BASE}/feed?limit=100`);
}
