import { describe, expect, it } from "vitest";
import {
  BUBBLE_MS,
  FADE_MS,
  GAP_MS,
  LEAD_MS,
  SpeechScheduler,
  toSpeech,
  truncate,
  twoSentences,
} from "./speech";
import type { CommsMessage, Conversation } from "./types";

function message(overrides: Partial<CommsMessage>): CommsMessage {
  return {
    message_id: "m1",
    conversation_id: "c1",
    seq: 1,
    thread_id: null,
    sender_id: "RISK-01",
    sender_name: "Aegis",
    sender_kind: "agent",
    recipient_ids: [],
    kind: "reply",
    origin: "tool_verified",
    origin_label: "verified from local records",
    timestamp: "2026-11-09T12:00:00Z",
    correlation_id: "x",
    task_id: null,
    decision_id: null,
    tool_call_id: null,
    content: "Aegis, Risk desk. Nothing is running on this desk.",
    status: "delivered",
    visibility: "conversation",
    citations: [],
    meta: {},
    ...overrides,
  };
}

function conversation(kind: Conversation["kind"], codes: string[]): Conversation {
  return {
    conversation_id: "c1",
    kind,
    title: "t",
    topic: "t",
    status: "open",
    pinned: false,
    created_by: "human",
    owner_id: null,
    max_rounds: 2,
    max_messages: 40,
    created_at: "",
    updated_at: "",
    closed_at: null,
    message_count: 1,
    unread: 0,
    agenda: null,
    last_message: null,
    members: codes.map((code) => ({
      member_id: code,
      member_name: code,
      member_kind: "agent" as const,
      role: "participant",
      last_read_seq: 0,
    })),
  };
}

describe("speech from persisted messages", () => {
  it("speaks the stored text, tagged with its origin, never a canned line", () => {
    const speech = toSpeech(message({}), conversation("direct", ["RISK-01"]));
    expect(speech?.text).toBe("Aegis, Risk desk. Nothing is running on this desk.");
    expect(speech?.label).toBe("verified");
    expect(speech?.code).toBe("RISK-01");
  });

  it("tags simulated and scripted rows so they are never shown as verified", () => {
    expect(toSpeech(message({ origin: "simulated" }), undefined)?.label).toBe("simulated");
    expect(toSpeech(message({ origin: "scripted" }), undefined)?.label).toBe("scripted");
  });

  it("does not speak for the human, the system, or an unknown sender", () => {
    expect(toSpeech(message({ sender_kind: "human", sender_id: "HUMAN", origin: "human" }), undefined)).toBeNull();
    expect(toSpeech(message({ sender_kind: "system", sender_id: "SYSTEM" }), undefined)).toBeNull();
    expect(toSpeech(message({ sender_id: "ROGUE-01" }), undefined)).toBeNull();
  });

  it("turns bullets into separators and drops citation markers", () => {
    expect(truncate("Head.\n- first fact [1]\n- second fact [2]")).toBe("Head. · first fact · second fact");
  });

  it("truncates long text with an ellipsis", () => {
    const text = truncate("word ".repeat(100), 40);
    expect(text.length).toBeLessThanOrEqual(40);
    expect(text.endsWith("…")).toBe(true);
    expect(truncate("short")).toBe("short");
  });

  it("keeps a bubble to two sentences", () => {
    expect(twoSentences("One. Two. Three stays in the transcript.")).toBe("One. Two.");
  });
});

describe("speech scheduler", () => {
  const talk = (id: string, code: string, conv: Conversation) =>
    toSpeech(message({ message_id: id, sender_id: code }), conv)!;

  it("shows a direct reply at once and lets it expire", () => {
    const scheduler = new SpeechScheduler();
    const conv = conversation("direct", ["RISK-01"]);
    scheduler.enqueue([talk("a", "RISK-01", conv)]);
    expect(scheduler.tick(0).speech["RISK-01"]?.id).toBe("a");
    expect(scheduler.tick(scheduler.life - 1).speech["RISK-01"]).toBeDefined();
    expect(scheduler.tick(scheduler.life + 1).speech["RISK-01"]).toBeUndefined();
    expect(scheduler.tick(scheduler.life + 1).gather).toEqual([]);
  });

  it("does not replay history that was marked seen, and ignores duplicates", () => {
    const scheduler = new SpeechScheduler();
    const conv = conversation("direct", ["RISK-01"]);
    scheduler.markSeen(["old"]);
    scheduler.enqueue([talk("old", "RISK-01", conv), talk("new", "RISK-01", conv), talk("new", "RISK-01", conv)]);
    expect(scheduler.pending()).toBe(1);
  });

  it("sends a discussion to the boardroom first, then speaks in stored order", () => {
    const scheduler = new SpeechScheduler();
    const conv = conversation("discussion", ["SUPERVISOR-01", "RISK-01", "STOCK-01"]);
    scheduler.enqueue([
      talk("1", "SUPERVISOR-01", conv),
      talk("2", "STOCK-01", conv),
      talk("3", "RISK-01", conv),
    ]);
    const first = scheduler.tick(0);
    expect(first.gather).toEqual(["SUPERVISOR-01", "RISK-01", "STOCK-01"]);
    expect(Object.keys(first.speech)).toEqual([]);
    expect(Object.keys(scheduler.tick(LEAD_MS - 1).speech)).toEqual([]);
    expect(Object.keys(scheduler.tick(LEAD_MS).speech)).toEqual(["SUPERVISOR-01"]);
    const second = scheduler.tick(LEAD_MS + GAP_MS);
    expect(second.speech["STOCK-01"]?.id).toBe("2");
    const third = scheduler.tick(LEAD_MS + 2 * GAP_MS);
    expect(third.speech["RISK-01"]?.id).toBe("3");
    expect(third.gather.length).toBe(3);
  });

  it("sends the desks home after the discussion ends", () => {
    const scheduler = new SpeechScheduler();
    const conv = conversation("boardroom", ["SUPERVISOR-01", "RISK-01"]);
    scheduler.enqueue([talk("1", "SUPERVISOR-01", conv)]);
    scheduler.tick(0);
    scheduler.tick(LEAD_MS);
    expect(scheduler.tick(LEAD_MS + 100).gather.length).toBe(2);
    expect(scheduler.tick(LEAD_MS + BUBBLE_MS + 4000).gather).toEqual([]);
  });

  it("showNow puts a stored message above the clicked avatar", () => {
    const scheduler = new SpeechScheduler();
    const conv = conversation("direct", ["DAY-01"]);
    scheduler.showNow(talk("z", "DAY-01", conv), 10);
    expect(scheduler.tick(11).speech["DAY-01"]?.id).toBe("z");
  });

  it("a newer line restarts the 5 second timer", () => {
    const scheduler = new SpeechScheduler(BUBBLE_MS + FADE_MS);
    const conv = conversation("direct", ["RISK-01"]);
    scheduler.showNow(talk("old", "RISK-01", conv), 0);
    scheduler.showNow(talk("new", "RISK-01", conv), 4000);
    expect(scheduler.tick(4000 + BUBBLE_MS).speech["RISK-01"]?.id).toBe("new");
    expect(scheduler.tick(4000 + scheduler.life + 1).speech["RISK-01"]).toBeUndefined();
  });

  it("repeats each desk's latest stored line once the queue is quiet", () => {
    const scheduler = new SpeechScheduler(1000);
    const conv = conversation("direct", ["RISK-01", "DAY-01"]);
    scheduler.replacePlaylist([talk("a", "RISK-01", conv), talk("b", "DAY-01", conv)]);
    const first = scheduler.tick(0);
    expect(first.speech["RISK-01"]?.id).toBe("a");
    expect(first.speech["DAY-01"]).toBeUndefined();
    expect(scheduler.tick(1000).speech["RISK-01"]).toBeUndefined();
    expect(scheduler.tick(1400).speech["DAY-01"]?.id).toBe("b");
    const again = scheduler.tick(2800);
    expect(again.speech["RISK-01"]?.id).toBe("a");
    expect(again.speech["RISK-01"]?.token).not.toBe(first.speech["RISK-01"]?.token);
  });

  it("plays a new stored line before repeating older lines", () => {
    const scheduler = new SpeechScheduler();
    const conv = conversation("direct", ["RISK-01", "DAY-01"]);
    scheduler.replacePlaylist([talk("old", "RISK-01", conv)]);
    scheduler.enqueue([talk("new", "DAY-01", conv)]);
    expect(scheduler.tick(0).speech["DAY-01"]?.id).toBe("new");
    expect(scheduler.tick(0).speech["RISK-01"]).toBeUndefined();
  });

  it("reduced motion drops the bubble at 5 seconds with no fade", () => {
    const scheduler = new SpeechScheduler(BUBBLE_MS);
    const conv = conversation("direct", ["ETF-01"]);
    scheduler.showNow(talk("a", "ETF-01", conv), 0);
    expect(scheduler.tick(BUBBLE_MS - 1).speech["ETF-01"]).toBeDefined();
    expect(scheduler.tick(BUBBLE_MS + 1).speech["ETF-01"]).toBeUndefined();
  });
});
