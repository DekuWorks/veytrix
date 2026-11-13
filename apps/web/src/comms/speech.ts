import { AGENT_CODES, type AgentCode } from "../api/types";
import { ORIGIN_TAG, type CommsMessage, type Conversation, type Speech } from "./types";

export const BUBBLE_MS = 5000;
/** Short fade after the 5 readable seconds. Reduced motion uses 0. */
export const FADE_MS = 400;
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
    peerReply: message.meta.peer_reply === true,
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
  /** How long a bubble stays mounted. Includes the fade, unless reduced motion turned that off. */
  readonly life: number;
  private queue: Speech[] = [];
  private active = new Map<AgentCode, { speech: Speech; until: number }>();
  /** Latest stored line per desk. Spoken one at a time when nothing newer is queued. */
  private playlist: Speech[] = [];
  private playlistAt = 0;
  private token = 0;

  constructor(life = BUBBLE_MS + FADE_MS) {
    this.life = life;
  }
  private nextAt = 0;
  private gatherConversation: string | null = null;
  private gatherCodes: AgentCode[] = [];
  private lastSpoke = Number.NEGATIVE_INFINITY;
  readonly seen = new Set<string>();

  /** Mark rows as already shown (the first load must not replay history). */
  markSeen(ids: string[]): void {
    ids.forEach((id) => this.seen.add(id));
  }

  /** Returns only the lines that were not already seen. */
  enqueue(items: Speech[]): Speech[] {
    const added: Speech[] = [];
    for (const item of items) {
      if (this.seen.has(item.id)) {
        continue;
      }
      this.seen.add(item.id);
      this.queue.push(item);
      added.push(item);
    }
    return added;
  }

  /** Show one stored message now. A newer line for the same avatar restarts the timer. */
  showNow(item: Speech, now: number): void {
    this.present(item, now);
  }

  /** Replace the lines the floor repeats. These are stored messages, not new text. */
  replacePlaylist(items: Speech[]): void {
    this.playlist = items;
  }

  /** Keep a newly stored line in the rotation. */
  upsertPlaylist(items: Speech[]): void {
    const map = new Map(this.playlist.map((item) => [item.code, item]));
    for (const item of items) {
      map.set(item.code, item);
    }
    this.playlist = [...map.values()];
  }

  clear(): void {
    this.queue = [];
    this.active.clear();
    this.gatherConversation = null;
    this.gatherCodes = [];
  }

  private present(item: Speech, now: number): void {
    this.token += 1;
    this.active.set(item.code, { speech: { ...item, token: this.token }, until: now + this.life });
    this.lastSpoke = now;
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
        this.present(head, now);
        this.nextAt = now + GAP_MS;
      }
    }
    if (
      this.queue.length === 0 &&
      this.active.size === 0 &&
      this.playlist.length > 0 &&
      now >= this.nextAt &&
      now >= this.lastSpoke + this.life + 400
    ) {
      const item = this.playlist[this.playlistAt % this.playlist.length];
      this.playlistAt += 1;
      this.present(item, now);
      this.nextAt = now + this.life + 400;
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
