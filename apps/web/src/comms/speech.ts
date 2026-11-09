import { AGENT_CODES, type AgentCode } from "../api/types";
import { ORIGIN_TAG, type CommsMessage, type Conversation, type Speech } from "./types";

export const BUBBLE_MS = 6000;
export const GAP_MS = 3500;
export const LEAD_MS = 4000;
export const LINGER_MS = 3000;
export const BUBBLE_CHARS = 150;

const GATHERING = new Set(["discussion", "boardroom"]);

/** One line for a bubble or a feed row: bullets become separators and [n] markers are dropped. */
export function truncate(text: string, limit = BUBBLE_CHARS): string {
  const flat = text
    .replace(/\n- /g, " · ")
    .replace(/\s*\[\d+\]/g, "")
    .replace(/\s+/g, " ")
    .trim();
  return flat.length <= limit ? flat : `${flat.slice(0, limit - 1).trimEnd()}…`;
}

function isAgentCode(value: string): value is AgentCode {
  return (AGENT_CODES as readonly string[]).includes(value);
}

/** A bubble comes only from a persisted agent message. Human and system rows never speak. */
export function toSpeech(
  message: CommsMessage,
  conversation: Conversation | undefined,
  replay = false,
): Speech | null {
  if (message.sender_kind !== "agent" || !isAgentCode(message.sender_id)) {
    return null;
  }
  const participants = (conversation?.members ?? [])
    .filter((member) => member.member_kind === "agent" && isAgentCode(member.member_id))
    .map((member) => member.member_id as AgentCode);
  return {
    id: message.message_id,
    code: message.sender_id,
    text: truncate(message.content),
    origin: message.origin,
    label: ORIGIN_TAG[message.origin],
    conversationId: message.conversation_id,
    conversationKind: conversation?.kind ?? "unknown",
    participants,
    replay,
  };
}

export type SpeechFrame = {
  speech: Record<string, Speech>;
  gather: AgentCode[];
};

/**
 * Plays persisted messages one speaker at a time. A discussion first sends its members to the
 * boardroom, waits LEAD_MS, then speaks the messages in stored order. Nothing here invents text.
 */
export class SpeechScheduler {
  private queue: Speech[] = [];
  private active = new Map<AgentCode, { speech: Speech; until: number }>();
  private nextAt = 0;
  private gatherConversation: string | null = null;
  private gatherCodes: AgentCode[] = [];
  private lastSpoke = 0;
  readonly seen = new Set<string>();

  /** Mark rows as already shown (the first load must not replay history). */
  markSeen(ids: string[]): void {
    ids.forEach((id) => this.seen.add(id));
  }

  enqueue(items: Speech[]): void {
    for (const item of items) {
      if (this.seen.has(item.id)) {
        continue;
      }
      this.seen.add(item.id);
      this.queue.push(item);
    }
  }

  /** Show one stored message now, for example when the user clicks an avatar. */
  showNow(item: Speech, now: number): void {
    this.active.set(item.code, { speech: item, until: now + BUBBLE_MS });
    this.lastSpoke = now;
  }

  clear(): void {
    this.queue = [];
    this.active.clear();
    this.gatherConversation = null;
    this.gatherCodes = [];
  }

  pending(): number {
    return this.queue.length;
  }

  tick(now: number): SpeechFrame {
    for (const [code, entry] of this.active) {
      if (entry.until <= now) {
        this.active.delete(code);
      }
    }
    const head = this.queue[0];
    if (head && now >= this.nextAt) {
      const gathers = GATHERING.has(head.conversationKind);
      if (gathers && this.gatherConversation !== head.conversationId) {
        this.gatherConversation = head.conversationId;
        this.gatherCodes = head.participants;
        this.nextAt = now + LEAD_MS;
      } else {
        this.queue.shift();
        this.active.set(head.code, { speech: head, until: now + BUBBLE_MS });
        this.nextAt = now + GAP_MS;
        this.lastSpoke = now;
      }
    }
    if (
      this.gatherConversation !== null &&
      !this.queue.some((item) => item.conversationId === this.gatherConversation) &&
      now - this.lastSpoke > LINGER_MS &&
      this.active.size === 0
    ) {
      this.gatherConversation = null;
      this.gatherCodes = [];
    }
    const speech: Record<string, Speech> = {};
    for (const [code, entry] of this.active) {
      speech[code] = entry.speech;
    }
    return { speech, gather: this.gatherCodes };
  }
}
