import { useCallback, useEffect, useRef, useState } from "react";
import type { AgentCode } from "../api/types";
import { openCommsChannel } from "../sanctum/realtime";
import { getFlags, listConversations, loadFeed, startFloor } from "./api";
import { BUBBLE_MS, FADE_MS, SpeechScheduler, toSpeech, type SpeechFrame } from "./speech";
import type { CommsMessage, Conversation, Flags, SendResult } from "./types";

export type RealtimeState = "not_configured" | "connecting" | "connected" | "polling";

const POLL_MS = 3000;
const POLL_WITH_DOORBELL_MS = 20_000;
const FEED_KEEP = 100;

function sameFrame(a: SpeechFrame, b: SpeechFrame): boolean {
  const ids = (frame: SpeechFrame) =>
    Object.entries(frame.speech)
      .map(([code, item]) => `${code}:${item.id}`)
      .sort()
      .join("|");
  return ids(a) === ids(b) && a.gather.join(",") === b.gather.join(",");
}

export type CommsState = {
  available: boolean;
  flags: Flags | null;
  realtime: RealtimeState;
  conversations: Conversation[];
  feed: CommsMessage[];
  frame: SpeechFrame;
  notice: string;
  refresh: () => Promise<void>;
  ingest: (result: SendResult) => void;
  speakLast: (code: AgentCode) => boolean;
  replayMessage: (message: CommsMessage, conversation: Conversation | undefined) => void;
  stopReplay: () => void;
};

/** Polls the local API for stored messages, optionally rings a Realtime doorbell, and plays them. */
export function useComms(): CommsState {
  const reduceMotion =
    typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const scheduler = useRef(new SpeechScheduler(BUBBLE_MS + (reduceMotion ? 0 : FADE_MS)));
  const shifted = useRef(false);
  const first = useRef(true);
  const lastByCode = useRef<Map<string, CommsMessage>>(new Map());
  const convs = useRef<Map<string, Conversation>>(new Map());
  const [available, setAvailable] = useState(true);
  const [flags, setFlags] = useState<Flags | null>(null);
  const [realtime, setRealtime] = useState<RealtimeState>("not_configured");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [feed, setFeed] = useState<CommsMessage[]>([]);
  const [frame, setFrame] = useState<SpeechFrame>({ speech: {}, gather: [] });
  const [notice, setNotice] = useState("");

  const remember = useCallback((messages: CommsMessage[]) => {
    for (const message of messages) {
      if (message.sender_kind === "agent") {
        const known = lastByCode.current.get(message.sender_id);
        if (!known || known.timestamp <= message.timestamp) {
          lastByCode.current.set(message.sender_id, message);
        }
      }
    }
  }, []);

  const refresh = useCallback(async () => {
    try {
      if (!shifted.current) {
        shifted.current = true;
        try {
          await startFloor();
        } catch {
          // The feed still loads. A failed report is not a reason to invent speech.
        }
      }
      const [feedBody, list] = await Promise.all([loadFeed(), listConversations()]);
      list.forEach((conv) => convs.current.set(conv.conversation_id, conv));
      setConversations(list);
      remember(feedBody.messages);
      const speeches = feedBody.messages
        .map((message) => toSpeech(message, convs.current.get(message.conversation_id)))
        .filter((item): item is NonNullable<typeof item> => item !== null);
      const latest = new Map<string, (typeof speeches)[number]>();
      for (const item of speeches) {
        latest.set(item.code, item);
      }
      scheduler.current.replacePlaylist([...latest.values()]);
      if (first.current) {
        scheduler.current.markSeen(feedBody.messages.map((m) => m.message_id));
        const newestTask = [...feedBody.messages]
          .reverse()
          .find((message) => message.meta.desk_task === true);
        const spoken = newestTask
          ? toSpeech(newestTask, convs.current.get(newestTask.conversation_id))
          : speeches[speeches.length - 1];
        if (spoken) {
          scheduler.current.showNow(spoken, Date.now());
        }
        first.current = false;
        setFrame(scheduler.current.tick(Date.now()));
      } else {
        scheduler.current.enqueue(speeches);
      }
      setFeed(feedBody.messages.slice(-FEED_KEEP));
      setAvailable(true);
    } catch {
      setAvailable(false);
    }
  }, [remember]);

  useEffect(() => {
    let cancelled = false;
    void getFlags()
      .then((body) => {
        if (!cancelled) {
          setFlags(body);
          setRealtime(body.realtime === "configured" ? "connecting" : "not_configured");
        }
      })
      .catch(() => {
        if (!cancelled) {
          setAvailable(false);
        }
      });
    void refresh();
    return () => {
      cancelled = true;
    };
  }, [refresh]);

  useEffect(() => {
    if (flags?.realtime !== "configured") {
      return undefined;
    }
    let close: (() => void) | undefined;
    let dead = false;
    void openCommsChannel(
      { url: import.meta.env.VITE_SUPABASE_URL, anonKey: import.meta.env.VITE_SUPABASE_ANON_KEY },
      () => {
        void refresh();
      },
    ).then((channel) => {
      if (dead) {
        channel.close();
        return;
      }
      close = channel.close;
      setRealtime(channel.mode === "realtime" ? "connected" : "polling");
    });
    return () => {
      dead = true;
      close?.();
    };
  }, [flags, refresh]);

  useEffect(() => {
    const interval = realtime === "connected" ? POLL_WITH_DOORBELL_MS : POLL_MS;
    const id = window.setInterval(() => void refresh(), interval);
    return () => window.clearInterval(id);
  }, [realtime, refresh]);

  useEffect(() => {
    const id = window.setInterval(() => {
      const next = scheduler.current.tick(Date.now());
      setFrame((current) => (sameFrame(current, next) ? current : next));
    }, 500);
    return () => window.clearInterval(id);
  }, []);

  const ingest = useCallback(
    (result: SendResult) => {
      convs.current.set(result.conversation.conversation_id, result.conversation);
      setConversations((current) => {
        const rest = current.filter((c) => c.conversation_id !== result.conversation.conversation_id);
        return [result.conversation, ...rest];
      });
      remember(result.messages);
      const items = result.messages
        .map((message) => toSpeech(message, result.conversation))
        .filter((item): item is NonNullable<typeof item> => item !== null);
      scheduler.current.enqueue(items);
      scheduler.current.upsertPlaylist(items);
    },
    [remember],
  );

  const speakLast = useCallback((code: AgentCode): boolean => {
    const message = lastByCode.current.get(code);
    if (!message) {
      setNotice(`${code} has no stored message yet. Open the chat and ask a question.`);
      return false;
    }
    setNotice("");
    const speech = toSpeech(message, convs.current.get(message.conversation_id));
    if (speech) {
      scheduler.current.showNow(speech, Date.now());
      setFrame(scheduler.current.tick(Date.now()));
    }
    return true;
  }, []);

  const replayMessage = useCallback((message: CommsMessage, conversation: Conversation | undefined) => {
    const speech = toSpeech(message, conversation, true);
    if (speech) {
      scheduler.current.showNow({ ...speech, id: `replay-${speech.id}-${Date.now()}` }, Date.now());
      setFrame(scheduler.current.tick(Date.now()));
    }
  }, []);

  const stopReplay = useCallback(() => {
    scheduler.current.clear();
    setFrame({ speech: {}, gather: [] });
  }, []);

  return {
    available,
    flags,
    realtime,
    conversations,
    feed,
    frame,
    notice,
    refresh,
    ingest,
    speakLast,
    replayMessage,
    stopReplay,
  };
}
