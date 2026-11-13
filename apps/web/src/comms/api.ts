import { apiGet, apiPatch, apiPost } from "../api/client";
import type { AgentCode } from "../api/types";
import { takeEvents } from "./stream";
import type {
  CommsMessage,
  Conversation,
  Flags,
  SendResult,
} from "./types";

const BASE = "/api/v1/comms";
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

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

export type TaskRow = {
  id: string;
  assignee_code: string;
  subject: string;
  status: "queued" | "running" | "blocked" | "completed" | "failed";
  kind: "research" | "review";
  evidence_message_id: string | null;
  blocked_reason: string | null;
  attempt_count: number;
};

export function loadTasks(conversationId?: string): Promise<TaskRow[]> {
  const suffix = conversationId ? `?conversation_id=${conversationId}` : "";
  return apiGet<{ tasks: TaskRow[] }>(`${BASE}/tasks${suffix}`).then((body) => body.tasks);
}

export async function sendMessageStream(
  conversationId: string,
  content: string,
  handlers: {
    onChunk: (text: string) => void;
    signal?: AbortSignal;
  },
): Promise<SendResult> {
  const response = await fetch(`${API_BASE}${BASE}/conversations/${conversationId}/messages/stream`, {
    method: "POST",
    headers: {
      Accept: "text/event-stream",
      "Content-Type": "application/json",
      "X-Correlation-ID": crypto.randomUUID(),
    },
    body: JSON.stringify({
      content,
      client_message_id: crypto.randomUUID().replace(/-/g, "").slice(0, 32),
    }),
    credentials: "omit",
    signal: handlers.signal,
  });
  if (!response.ok || response.body === null) {
    throw new Error(`The stream answered ${response.status}.`);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result: SendResult | null = null;
  while (true) {
    const step = await reader.read();
    if (step.done) {
      break;
    }
    buffer += decoder.decode(step.value, { stream: true });
    const taken = takeEvents(buffer);
    buffer = taken.rest;
    for (const item of taken.events) {
      const payload = JSON.parse(item.data) as Record<string, unknown>;
      if (item.event === "chunk" && typeof payload.text === "string") {
        handlers.onChunk(payload.text);
      } else if (item.event === "error") {
        throw new Error(typeof payload.detail === "string" ? payload.detail : "The stream failed.");
      } else if (item.event === "done") {
        result = payload as unknown as SendResult;
      }
    }
  }
  if (result === null) {
    throw new Error("The stream ended before a stored reply.");
  }
  return result;
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
