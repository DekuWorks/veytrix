import { useCallback, useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { ApiError, errorDetail } from "../../api/client";
import type { AgentCode } from "../../api/types";
import { loadMessages, markRead, openDirect, sendMessage } from "../../comms/api";
import type { CommsMessage, Conversation, SendResult } from "../../comms/types";
import { ChatThread } from "./ChatThread";
import "./comms.css";

const QUICK = [
  "What are you working on?",
  "Show sources",
  "What actions were actually executed?",
  "Explain this",
  "What is a stop loss?",
] as const;

type ChatPanelProps = {
  code: AgentCode;
  name: string;
  role: string;
  status: string;
  floating: boolean;
  following: boolean;
  onFollow: (value: boolean) => void;
  onResult: (result: SendResult) => void;
  onClose?: () => void;
};

function failure(error: unknown): string {
  if (error instanceof ApiError) {
    return errorDetail(error.body) ?? `The API answered ${error.status}.`;
  }
  return "The API is not reachable. Nothing was sent.";
}

/** Two-way chat with one desk. Every line shown here was read back from the stored transcript. */
export function ChatPanel({
  code,
  name,
  role,
  status,
  floating,
  following,
  onFollow,
  onResult,
  onClose,
}: ChatPanelProps) {
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<CommsMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const box = useRef<HTMLTextAreaElement>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const conv = await openDirect(code);
      const rows = await loadMessages(conv.conversation_id);
      setConversation(conv);
      setMessages(rows);
      if (rows.length > 0) {
        void markRead(conv.conversation_id, rows[rows.length - 1].seq).catch(() => undefined);
      }
    } catch (caught) {
      setConversation(null);
      setMessages([]);
      setError(failure(caught));
    } finally {
      setLoading(false);
    }
  }, [code]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!loading && !error) {
      box.current?.focus();
    }
  }, [loading, error, code]);

  async function send(text: string) {
    const content = text.trim();
    if (!content || busy) {
      return;
    }
    setBusy(true);
    setFailed(null);
    setNote(null);
    try {
      const conv = conversation ?? (await openDirect(code));
      if (!conversation) {
        setConversation(conv);
        setError(null);
      }
      const result = await sendMessage(conv.conversation_id, content);
      setConversation(result.conversation);
      setMessages((current) => {
        const known = new Set(current.map((m) => m.message_id));
        return [...current, ...result.messages.filter((m) => !known.has(m.message_id))];
      });
      setDraft("");
      onResult(result);
      if (result.errors.length > 0) {
        setNote(`Not every reply was written: ${result.errors.join(", ")}.`);
      }
    } catch (caught) {
      setFailed(content);
      setNote(failure(caught));
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void send(draft);
  }

  function onKey(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      void send(draft);
    }
  }

  return (
    <section
      role="dialog"
      aria-label={`Chat with ${name}`}
      className={`cx-panel ${floating ? "desk-dialog" : "view-card"}`}
    >
      <header className="cx-head">
        <p>
          <strong>{name}</strong>
          <span className="sx-k">
            {" "}
            {code} · {role}
          </span>
        </p>
        <label className="cx-follow">
          <input type="checkbox" checked={following} onChange={(event) => onFollow(event.target.checked)} />
          Follow on floor
        </label>
        {floating && onClose ? (
          <button type="button" className="vx-btn" onClick={onClose}>
            Close detail
          </button>
        ) : null}
      </header>
      <p className="sx-note">
        {status}. Claude is offline. A verified tag is local records, not a model. No order is sent.
      </p>
      {loading ? <p className="cx-empty">Opening the conversation…</p> : null}
      {error ? (
        <div className="cx-error" role="alert">
          <p>History did not load. {error} You can still type below.</p>
          <button type="button" className="vx-btn" onClick={() => void load()}>
            Retry
          </button>
        </div>
      ) : null}
      <>
          <ChatThread
            label={`Transcript with ${name}`}
            messages={messages}
            pending={busy ? name : null}
            empty={`No messages with ${name} yet. Ask a question below.`}
          />
          <div className="task-row" role="group" aria-label="Quick questions">
            {QUICK.map((question) => (
              <button
                key={question}
                type="button"
                className="vx-btn"
                disabled={busy}
                onClick={() => void send(question)}
              >
                {question}
              </button>
            ))}
          </div>
          {note ? (
            <p className="cx-note" role="status">
              {note}
              {failed ? (
                <>
                  {" "}
                  <button type="button" className="vx-btn" onClick={() => void send(failed)}>
                    Retry message
                  </button>
                </>
              ) : null}
            </p>
          ) : null}
          <form className="cx-composer" onSubmit={onSubmit}>
            <label className="sr-only" htmlFor={`cx-draft-${code}`}>
              Message {name}
            </label>
            <textarea
              id={`cx-draft-${code}`}
              ref={box}
              aria-label={`Message ${name}`}
              maxLength={1000}
              rows={2}
              value={draft}
              placeholder={`Ask ${name}. It cannot place an order. Ctrl+Enter sends.`}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={onKey}
            />
            <button type="submit" className="vx-btn" disabled={busy || draft.trim().length === 0}>
              {busy ? "Sending…" : "Send"}
            </button>
          </form>
      </>
    </section>
  );
}
