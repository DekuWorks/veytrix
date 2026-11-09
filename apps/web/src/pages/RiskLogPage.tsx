import { useEffect, useState } from "react";
import { apiGet } from "../api/client";
import type { RiskEventLogResponse } from "../api/types";

const UNAVAILABLE = "The risk event log is unavailable. No order was recorded.";

type LoadState =
  | { status: "loading" }
  | { status: "unavailable" }
  | { status: "ready"; payload: RiskEventLogResponse };

function isLog(value: RiskEventLogResponse): boolean {
  const kinds = value.unlogged.map((item) => item.kind);
  return (
    value.persisted_action === "risk.size.recorded" &&
    value.shield_persisted === false &&
    value.reservation_persisted === false &&
    value.execution_permitted === false &&
    value.order_submitted === false &&
    value.source === "local_audit_log" &&
    value.note.length > 0 &&
    kinds.join(",") === "shield_preview,reservation_preview" &&
    value.unlogged.every((item) => item.persisted === false) &&
    value.events.every(
      (event) =>
        event.action === "risk.size.recorded" &&
        event.execution_permitted === false &&
        event.order_submitted === false,
    )
  );
}

export function RiskLogPage() {
  const [state, setState] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    document.title = "Risk log · Veytrix";
  }, []);

  useEffect(() => {
    let cancelled = false;
    apiGet<RiskEventLogResponse>("/api/v1/risk/log")
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setState(isLog(payload) ? { status: "ready", payload } : { status: "unavailable" });
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

  const log = state.status === "ready" ? state.payload : null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Risk log</h1>
        <p className="mt-2 max-w-3xl text-sm text-muted">
          Stored size calculations are listed. Shield and reservation previews are not written.
          This page cannot submit an order.
        </p>
      </div>
      {state.status === "loading" ? <p className="text-sm text-muted">Loading the risk log.</p> : null}
      {state.status === "unavailable" ? (
        <p className="text-sm text-danger" role="alert">
          {UNAVAILABLE}
        </p>
      ) : null}
      {log ? (
        <>
          <ul className="max-w-xl space-y-2 text-sm">
            {log.unlogged.map((item) => (
              <li key={item.kind} className="rounded-md border border-line bg-panel px-4 py-3">
                <span className="font-mono">{item.kind}</span>
                <span className="text-muted"> · not stored</span>
              </li>
            ))}
          </ul>
          {log.events.length === 0 ? (
            <p className="text-sm text-muted">No stored size events.</p>
          ) : (
            <table className="w-full max-w-xl border-collapse text-sm">
              <caption className="sr-only">Stored size events</caption>
              <thead>
                <tr className="border-b border-line text-left text-muted">
                  <th className="py-2 pr-4 font-medium">Symbol</th>
                  <th className="py-2 pr-4 font-medium">Shares</th>
                  <th className="py-2 font-medium">Order submitted</th>
                </tr>
              </thead>
              <tbody>
                {log.events.map((event) => (
                  <tr key={event.id} className="border-b border-line">
                    <td className="py-2 pr-4 font-mono">{event.symbol}</td>
                    <td className="py-2 pr-4 font-mono">{event.shares}</td>
                    <td className="py-2 font-mono">{String(event.order_submitted)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <p className="max-w-3xl text-sm text-muted">{log.note}</p>
        </>
      ) : null}
    </div>
  );
}
