import { useEffect, useState } from "react";
import { apiGet } from "../api/client";
import type { SupervisorToolsResponse } from "../api/types";

const UNAVAILABLE = "Supervisor tools are unavailable. No chat box was invented.";

const READ_TOOLS = [
  "read_system_status",
  "read_agents",
  "read_desk",
  "read_market_health",
  "read_treasury_summary",
  "read_audit_log",
  "read_research_notes",
] as const;

const DENY_TOOLS = [
  "submit_order",
  "cancel_order",
  "sign_transaction",
  "broadcast_transaction",
  "bank_transfer",
  "set_live_mode",
  "release_kill_switch",
  "enable_agent",
  "approve_payout",
  "size_position",
  "supervisor_chat",
] as const;

type LoadState =
  | { status: "loading" }
  | { status: "unavailable" }
  | { status: "ready"; payload: SupervisorToolsResponse };

function isCatalogue(value: SupervisorToolsResponse): boolean {
  const expected = [...READ_TOOLS, ...DENY_TOOLS];
  if (
    value.source !== "local_catalogue" ||
    value.model !== "not_configured" ||
    value.chat !== "absent" ||
    value.executed !== false ||
    value.invokes_model !== false ||
    value.execution_permitted !== false ||
    value.order_submitted !== false ||
    value.tools.length !== expected.length
  ) {
    return false;
  }
  return value.tools.every((tool, index) => {
    const effect = index < READ_TOOLS.length ? "read" : "deny";
    return tool.name === expected[index] && tool.effect === effect && tool.executes === false;
  });
}

export function SupervisorPage() {
  const [state, setState] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    document.title = "Supervisor · Veytrix";
  }, []);

  useEffect(() => {
    let cancelled = false;
    apiGet<SupervisorToolsResponse>("/api/v1/supervisor/tools")
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setState(isCatalogue(payload) ? { status: "ready", payload } : { status: "unavailable" });
      })
      .catch(() => {
        if (!cancelled) {
          setState({ status: "unavailable" });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const ready = state.status === "ready" ? state.payload : null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Supervisor</h1>
        <p className="mt-2 max-w-3xl text-sm text-muted">
          This page lists local tools. Chat is not configured. Nothing here runs a tool or calls a
          model.
        </p>
      </div>
      {state.status === "loading" ? <p className="text-sm text-muted">Loading supervisor tools.</p> : null}
      {state.status === "unavailable" ? (
        <p className="text-sm text-danger" role="alert">
          {UNAVAILABLE}
        </p>
      ) : null}
      {ready ? (
        <section aria-labelledby="supervisor-tools" className="space-y-4">
          <h2 id="supervisor-tools" className="text-lg font-semibold">
            Local catalogue. Chat is absent. Nothing on this page can run.
          </h2>
          <dl className="grid max-w-xl gap-3 rounded-md border border-line bg-panel p-4 text-sm">
            <div className="flex justify-between gap-4">
              <dt>Model</dt>
              <dd className="font-mono">{ready.model}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>Chat</dt>
              <dd className="font-mono">{ready.chat}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>Invokes a model</dt>
              <dd className="font-mono">{String(ready.invokes_model)}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>Execution permitted</dt>
              <dd className="font-mono">{String(ready.execution_permitted)}</dd>
            </div>
          </dl>
          <ul className="max-w-xl divide-y divide-line rounded-md border border-line bg-panel text-sm">
            {ready.tools.map((tool) => (
              <li key={tool.name} className="flex justify-between gap-4 px-4 py-2">
                <span className="font-mono">{tool.name}</span>
                <span className="font-mono">{tool.effect}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
