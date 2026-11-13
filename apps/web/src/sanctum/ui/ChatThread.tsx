import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { ORIGIN_TAG, type CommsMessage } from "../../comms/types";
import "./comms.css";

/**
 * Structure adapted from 21st.dev "Message Thread" (id 31661, MIT, Mohammad Shehadeh, Hirael).
 * Kept: the role="log" live region, follow-the-newest with a "Jump to latest" control, per-message
 * numbered sources, the typing indicator, and reduced-motion handling. Dropped: lucide-react,
 * shadcn Collapsible/Button, the copy and thumbs actions, and the reasoning block. No model
 * reasoning exists in this build and none is shown. Styles live in comms.css on the Sanctum palette.
 */

const KIND_LABEL: Record<string, string> = {
  claim: "thesis",
  objection: "objection",
  evidence: "evidence",
  risk_assessment: "risk assessment",
  recommendation: "recommendation",
  summary: "summary",
  assignment: "proposed task",
  refusal: "refused",
  clarification: "question",
  question: "question",
  notice: "notice",
  status: "status",
};

export function formatTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(date);
}

function Diagnostics({ message }: { message: CommsMessage }) {
  const raw = message.meta.diagnostics;
  if (raw === null || typeof raw !== "object" || Array.isArray(raw)) {
    return null;
  }
  const row = raw as Record<string, unknown>;
  const records = Array.isArray(row.records) ? row.records.map((item) => String(item)) : [];
  return (
    <details className="cx-sources">
      <summary>Diagnostics</summary>
      <ul>
        <li>Registry status: {String(row.registry_status ?? "unread")}</li>
        <li>Can submit orders: {String(row.can_submit_orders ?? false)}</li>
        <li>Can sign: {String(row.can_sign ?? false)}</li>
        <li>Can transfer funds: {String(row.can_transfer_funds ?? false)}</li>
        <li>Holds credentials: {String(row.holds_credentials ?? false)}</li>
        {records.map((item, index) => (
          <li key={`${index}-${item}`}>{item}</li>
        ))}
      </ul>
    </details>
  );
}

function Sources({ message }: { message: CommsMessage }) {
  if (message.citations.length === 0) {
    return null;
  }
  return (
    <details className="cx-sources">
      <summary>Sources ({message.citations.length})</summary>
      <ol>
        {message.citations.map((cite, index) => (
          <li key={`${cite.source}-${cite.ref}-${index}`}>
            <span>{cite.label}</span>
            <small>
              {cite.source} / {cite.ref}
              {cite.as_of ? `, as of ${cite.as_of}` : ""}
              {cite.untrusted ? ", untrusted text" : ""}
            </small>
          </li>
        ))}
      </ol>
    </details>
  );
}

export function MessageItem({ message, highlight }: { message: CommsMessage; highlight?: boolean }) {
  const mine = message.sender_kind === "human";
  const system = message.sender_kind === "system";
  const status = typeof message.meta.tool_status === "string" ? message.meta.tool_status : null;
  const position = typeof message.meta.position === "string" ? message.meta.position : null;
  return (
    <li
      className={`cx-msg ${mine ? "mine" : system ? "system" : "agent"}${highlight ? " now" : ""}`}
      data-origin={message.origin}
      data-kind={message.kind}
      data-seq={message.seq}
    >
      <header>
        <strong>{message.sender_name}</strong>
        {message.kind !== "reply" && message.kind !== "chat" && KIND_LABEL[message.kind] ? (
          <span className="cx-kind">{KIND_LABEL[message.kind]}</span>
        ) : null}
        <span className={`cx-origin o-${message.origin}`} title={message.origin_label}>
          {ORIGIN_TAG[message.origin]}
        </span>
        {status ? <span className="cx-chip">{status.replace(/_/g, " ")}</span> : null}
        {position ? <span className="cx-chip">{position.replace(/_/g, " ")}</span> : null}
        <time dateTime={message.timestamp}>{formatTime(message.timestamp)}</time>
      </header>
      <p>{message.content}</p>
      <Diagnostics message={message} />
      <Sources message={message} />
      {message.decision_id ? <small className="cx-decision">decision {message.decision_id}</small> : null}
    </li>
  );
}

type ChatThreadProps = {
  label: string;
  messages: CommsMessage[];
  /** Name of a desk that is composing, or null. */
  pending?: string | null;
  empty?: ReactNode;
  highlightSeq?: number | null;
};

export function ChatThread({ label, messages, pending = null, empty, highlightSeq = null }: ChatThreadProps) {
  const viewport = useRef<HTMLDivElement>(null);
  const pinned = useRef(true);
  const [atBottom, setAtBottom] = useState(true);

  useLayoutEffect(() => {
    const el = viewport.current;
    if (el && pinned.current) {
      el.scrollTop = el.scrollHeight;
    }
  }, [messages.length, pending]);

  useEffect(() => {
    const el = viewport.current;
    if (el && highlightSeq !== null) {
      el.querySelector(`[data-seq="${highlightSeq}"]`)?.scrollIntoView?.({ block: "nearest" });
    }
  }, [highlightSeq]);

  return (
    <div className="cx-thread-wrap">
      <div
        ref={viewport}
        className="cx-thread"
        role="log"
        aria-live="polite"
        aria-relevant="additions"
        aria-label={label}
        tabIndex={0}
        onScroll={() => {
          const el = viewport.current;
          if (!el) {
            return;
          }
          const near = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
          pinned.current = near;
          setAtBottom(near);
        }}
      >
        {messages.length === 0 && !pending ? <div className="cx-empty">{empty ?? "No messages yet."}</div> : null}
        <ul>
          {messages.map((message) => (
            <MessageItem key={message.message_id} message={message} highlight={highlightSeq === message.seq} />
          ))}
        </ul>
        {pending ? (
          <div className="cx-typing" role="status">
            <span aria-hidden="true">
              <i />
              <i />
              <i />
            </span>
            {pending} is writing
          </div>
        ) : null}
      </div>
      {!atBottom ? (
        <button
          type="button"
          className="vx-btn cx-jump"
          onClick={() => {
            const el = viewport.current;
            if (el) {
              pinned.current = true;
              el.scrollTop = el.scrollHeight;
              setAtBottom(true);
            }
          }}
        >
          Jump to latest
        </button>
      ) : null}
    </div>
  );
}
