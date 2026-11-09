import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { ApiError, errorDetail } from "../../api/client";
import {
  listConversations,
  loadMessages,
  markRead,
  moderate,
  openAllHands,
  patchConversation,
  sendMessage,
  startDiscussion,
} from "../../comms/api";
import type { CommsState } from "../../comms/useComms";
import type { CommsMessage, Conversation, SendResult } from "../../comms/types";
import { ChatThread, formatTime } from "./ChatThread";
import "./comms.css";

type Props = {
  comms: CommsState;
  onFollowAgent: (code: string | null) => void;
};

const KIND_LABEL: Record<Conversation["kind"], string> = {
  direct: "direct",
  group: "group",
  discussion: "discussion",
  boardroom: "boardroom",
};

function failure(error: unknown): string {
  if (error instanceof ApiError) {
    return errorDetail(error.body) ?? `The API answered ${error.status}.`;
  }
  return "The API is not reachable.";
}

export function ConversationMonitor({ comms, onFollowAgent }: Props) {
  const [query, setQuery] = useState("");
  const [archived, setArchived] = useState(false);
  const [shown, setShown] = useState<Conversation[] | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [messages, setMessages] = useState<CommsMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [topic, setTopic] = useState("");
  const [rounds, setRounds] = useState(2);
  const [draft, setDraft] = useState("");
  const [replay, setReplay] = useState<{ index: number; playing: boolean; speed: number } | null>(null);
  const timer = useRef<number | null>(null);

  const refreshList = useCallback(async () => {
    try {
      setShown(await listConversations(query || undefined, archived));
    } catch (caught) {
      setError(failure(caught));
    }
  }, [query, archived]);

  useEffect(() => {
    const id = window.setTimeout(() => void refreshList(), query ? 250 : 0);
    return () => window.clearTimeout(id);
  }, [refreshList, comms.conversations.length]);

  const list = shown ?? comms.conversations;
  const selected = useMemo(
    () => list.find((conv) => conv.conversation_id === selectedId) ?? null,
    [list, selectedId],
  );

  const open = useCallback(
    async (conversationId: string) => {
      setSelectedId(conversationId);
      setReplay(null);
      setError(null);
      try {
        const rows = await loadMessages(conversationId);
        setMessages(rows);
        if (rows.length > 0) {
          await markRead(conversationId, rows[rows.length - 1].seq);
        }
        const mine = rows.filter((row) => row.sender_kind === "agent").pop();
        onFollowAgent(mine ? mine.sender_id : null);
        await refreshList();
      } catch (caught) {
        setError(failure(caught));
      }
    },
    [onFollowAgent, refreshList],
  );

  function accept(result: SendResult, mode: "replace" | "append") {
    comms.ingest(result);
    if (mode === "replace") {
      setSelectedId(result.conversation.conversation_id);
      setMessages(result.messages);
    } else {
      setMessages((current) => {
        const known = new Set(current.map((m) => m.message_id));
        return [...current, ...result.messages.filter((m) => !known.has(m.message_id))];
      });
    }
    void refreshList();
  }

  async function run(action: () => Promise<SendResult>, mode: "replace" | "append") {
    setBusy(true);
    setError(null);
    try {
      accept(await action(), mode);
    } catch (caught) {
      setError(failure(caught));
    } finally {
      setBusy(false);
    }
  }

  async function openRoom(): Promise<SendResult> {
    const conv = await openAllHands();
    const rows = await loadMessages(conv.conversation_id);
    return {
      conversation: conv,
      messages: rows,
      duplicate: false,
      held: null,
      errors: [],
      realtime: "not_configured",
    };
  }

  function onStart(event: FormEvent<HTMLFormElement>, kind: "discussion" | "boardroom") {
    event.preventDefault();
    const text = topic.trim() || (kind === "boardroom" ? "Wednesday Boardroom" : "");
    if (text.length < 3) {
      setError("Give the discussion a topic of at least three characters.");
      return;
    }
    void run(() => startDiscussion(text, rounds, kind), "replace");
    setTopic("");
  }

  function onSend(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = draft.trim();
    if (!text || !selected) {
      return;
    }
    setDraft("");
    void run(() => sendMessage(selected.conversation_id, text), "append");
  }

  // Transcript replay. It plays stored rows with their real timestamps; it creates nothing.
  useEffect(() => {
    if (timer.current !== null) {
      window.clearInterval(timer.current);
      timer.current = null;
    }
    if (!replay?.playing) {
      return undefined;
    }
    timer.current = window.setInterval(() => {
      setReplay((current) => {
        if (!current || !current.playing) {
          return current;
        }
        const next = current.index + 1;
        if (next >= messages.length) {
          return { ...current, index: messages.length, playing: false };
        }
        comms.replayMessage(messages[next], selected ?? undefined);
        return { ...current, index: next };
      });
    }, 1600 / replay.speed);
    return () => {
      if (timer.current !== null) {
        window.clearInterval(timer.current);
      }
    };
  }, [replay?.playing, replay?.speed, messages, selected, comms]);

  const visible = replay ? messages.slice(0, replay.index + 1) : messages;
  const humanOnly = selected?.members.filter((m) => m.member_kind === "agent").length ?? 0;
  const paused = selected?.status === "paused";

  return (
    <div className="cx-monitor">
      <div className="cx-list">
        <h2>Conversation monitor</h2>
        <p className="sx-note">
          {comms.available ? "Live threads across all desks." : "The conversation API is not reachable."}{" "}
          {comms.realtime === "not_configured"
            ? "Supabase Realtime is not configured. Polling every 3 seconds."
            : comms.realtime === "connected"
              ? "Supabase Realtime doorbell connected."
              : "Supabase Realtime is configured but not connected. Polling."}
        </p>
        <label className="sr-only" htmlFor="cx-search">
          Search conversations
        </label>
        <input
          id="cx-search"
          type="search"
          className="cx-input"
          placeholder="Search conversations"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <label className="cx-follow">
          <input type="checkbox" checked={archived} onChange={(event) => setArchived(event.target.checked)} />
          Show archived
        </label>
        <div className="task-row">
          <button type="button" className="vx-btn" disabled={busy} onClick={() => void run(openRoom, "replace")}>
            Open the All desks room
          </button>
        </div>
        <form className="cx-start" onSubmit={(event) => onStart(event, "discussion")}>
          <label htmlFor="cx-topic">Start a desk discussion</label>
          <input
            id="cx-topic"
            className="cx-input"
            maxLength={200}
            placeholder="Topic, for example AAPL SMA crossover signals"
            value={topic}
            onChange={(event) => setTopic(event.target.value)}
          />
          <div className="task-row">
            <label>
              Rounds{" "}
              <select value={rounds} onChange={(event) => setRounds(Number(event.target.value))}>
                <option value={1}>1</option>
                <option value={2}>2</option>
                <option value={3}>3</option>
              </select>
            </label>
            <button type="submit" className="vx-btn" disabled={busy}>
              Start discussion
            </button>
            <button type="button" className="vx-btn" disabled={busy} onClick={(event) => onStart(event as unknown as FormEvent<HTMLFormElement>, "boardroom")}>
              Convene boardroom
            </button>
          </div>
          <p className="sx-note">
            Bounded rounds, rule-based and labelled simulated. No order or transfer can follow.
          </p>
        </form>
        {error ? (
          <p className="cx-note" role="alert">
            {error}
          </p>
        ) : null}
        <ul className="cx-convs" aria-label="Conversations">
          {list.length === 0 ? <li className="cx-empty">No conversations yet.</li> : null}
          {list.map((conv) => (
            <li key={conv.conversation_id}>
              <button
                type="button"
                aria-pressed={selectedId === conv.conversation_id}
                className="cx-conv"
                onClick={() => void open(conv.conversation_id)}
              >
                <strong>
                  {conv.pinned ? "📌 " : ""}
                  {conv.title}
                </strong>
                <span>
                  {KIND_LABEL[conv.kind]} · {conv.status} · {conv.message_count} msgs
                  {conv.unread > 0 ? <b className="cx-badge">{conv.unread} unread</b> : null}
                </span>
                {conv.last_message ? (
                  <small>
                    {conv.last_message.sender_name}: {conv.last_message.content.slice(0, 70)}
                  </small>
                ) : null}
              </button>
            </li>
          ))}
        </ul>
      </div>
      <div className="cx-detail">
        {!selected ? (
          <p className="cx-empty">Select a conversation to read the stored transcript.</p>
        ) : (
          <>
            <header className="cx-head">
              <p>
                <strong>{selected.title}</strong>
                <span className="sx-k">
                  {" "}
                  {KIND_LABEL[selected.kind]} · {selected.status} · {humanOnly} desks
                </span>
              </p>
            </header>
            <div className="task-row" role="group" aria-label="Conversation controls">
              <button
                type="button"
                className="vx-btn"
                aria-pressed={selected.pinned}
                onClick={() =>
                  void patchConversation(selected.conversation_id, { pinned: !selected.pinned })
                    .then(refreshList)
                    .catch((caught) => setError(failure(caught)))
                }
              >
                {selected.pinned ? "Unpin" : "Pin"}
              </button>
              <button
                type="button"
                className="vx-btn"
                onClick={() =>
                  void patchConversation(selected.conversation_id, { archived: selected.status !== "archived" })
                    .then(refreshList)
                    .catch((caught) => setError(failure(caught)))
                }
              >
                {selected.status === "archived" ? "Restore" : "Archive"}
              </button>
              {selected.kind !== "direct" && selected.status !== "archived" ? (
                <>
                  <button
                    type="button"
                    className="vx-btn"
                    disabled={busy || (selected.status !== "open" && selected.status !== "paused")}
                    onClick={() =>
                      void run(() => moderate(selected.conversation_id, paused ? "resume" : "pause"), "append")
                    }
                  >
                    {paused ? "Resume" : "Pause"}
                  </button>
                  <button
                    type="button"
                    className="vx-btn"
                    disabled={busy || selected.status === "closed"}
                    onClick={() => void run(() => moderate(selected.conversation_id, "close"), "append")}
                  >
                    Close
                  </button>
                </>
              ) : null}
              <button
                type="button"
                className="vx-btn"
                onClick={() => setReplay(replay ? null : { index: 0, playing: false, speed: 1 })}
              >
                {replay ? "Leave replay" : "Replay transcript"}
              </button>
            </div>
            {replay ? (
              <div className="task-row" role="group" aria-label="Replay controls">
                <button
                  type="button"
                  className="vx-btn"
                  onClick={() => setReplay({ ...replay, playing: !replay.playing, index: replay.index >= messages.length ? 0 : replay.index })}
                >
                  {replay.playing ? "Pause replay" : "Play"}
                </button>
                <button
                  type="button"
                  className="vx-btn"
                  disabled={replay.index + 1 >= messages.length}
                  onClick={() => {
                    const next = Math.min(messages.length - 1, replay.index + 1);
                    comms.replayMessage(messages[next], selected);
                    setReplay({ ...replay, index: next, playing: false });
                  }}
                >
                  Step
                </button>
                <button type="button" className="vx-btn" onClick={() => { comms.stopReplay(); setReplay({ index: 0, playing: false, speed: replay.speed }); }}>
                  Restart
                </button>
                <button
                  type="button"
                  className="vx-btn"
                  aria-pressed={replay.speed === 3}
                  onClick={() => setReplay({ ...replay, speed: replay.speed === 1 ? 3 : 1 })}
                >
                  3x
                </button>
                <span className="sx-k">
                  {Math.min(replay.index + 1, messages.length)} / {messages.length} · {visible.length > 0 ? formatTime(visible[visible.length - 1].timestamp) : ""}
                </span>
              </div>
            ) : null}
            <ChatThread
              label={`Transcript: ${selected.title}`}
              messages={visible}
              highlightSeq={replay ? visible[visible.length - 1]?.seq ?? null : null}
              empty="This conversation has no messages."
            />
            {selected.status !== "archived" && !replay ? (
              <form className="cx-composer" onSubmit={onSend}>
                <label className="sr-only" htmlFor="cx-monitor-draft">
                  Write in this conversation
                </label>
                <textarea
                  id="cx-monitor-draft"
                  rows={2}
                  maxLength={1000}
                  aria-label="Write in this conversation"
                  placeholder={
                    selected.kind === "direct"
                      ? "Ask this desk."
                      : paused
                        ? "Paused. Your message is stored; desks reply after Resume."
                        : "Ask a question. Mention a desk with @Astra, or everyone with @all."
                  }
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                />
                <button type="submit" className="vx-btn" disabled={busy || draft.trim().length === 0}>
                  Send
                </button>
              </form>
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}
