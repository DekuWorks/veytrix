import { useState, type FormEvent } from "react";

type AgentDockProps = {
  agentName: string;
  idleStatus: string;
  workingStatus: string;
  onMessageSubmit: (message: string) => Promise<string>;
};

/** Adapted from 21st.dev Agent Dock (demo 16632). Voice is omitted: this desk has no voice route. */
export function AgentDock({ agentName, idleStatus, workingStatus, onMessageSubmit }: AgentDockProps) {
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState("");
  const [status, setStatus] = useState(idleStatus);
  const [busy, setBusy] = useState(false);

  async function submit() {
    const next = message.trim();
    if (!next) {
      setOpen(true);
      return;
    }
    setMessage("");
    setBusy(true);
    setStatus(workingStatus);
    try {
      const result = await onMessageSubmit(next);
      setStatus(result);
    } catch {
      setStatus("Route failed. No order is sent.");
    } finally {
      setBusy(false);
      setOpen(false);
    }
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (open) {
      void submit();
      return;
    }
    setOpen(true);
  }

  return (
    <form className="rounded-md border border-line bg-obsidian p-2" onSubmit={onSubmit}>
      {open ? (
        <div className="relative mb-2">
          <button
            type="button"
            className="absolute right-1 top-1 text-xs text-muted"
            onClick={() => setOpen(false)}
          >
            Close composer
          </button>
          <textarea
            aria-label="Message agent"
            className="h-24 w-full resize-none bg-transparent pr-28 text-sm text-ink outline-none"
            placeholder="Ask this desk. It cannot place an order."
            value={message}
            onChange={(event) => setMessage(event.target.value)}
          />
        </div>
      ) : null}
      <div className="flex items-center gap-3">
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-ink">{agentName}</p>
          <p className="truncate text-xs text-muted">{busy ? workingStatus : status}</p>
        </div>
        <button type="submit" className="vx-btn">
          {open ? "Send" : "Chat"}
        </button>
      </div>
    </form>
  );
}
