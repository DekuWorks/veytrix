import { useEffect, useState } from "react";
import { apiGet } from "../api/client";
import type { ReconciliationResponse } from "../api/types";

const UNAVAILABLE = "Reconciliation is unavailable. No broker balance was invented.";

type LoadState =
  | { status: "loading" }
  | { status: "unavailable" }
  | { status: "ready"; payload: ReconciliationResponse };

function isMoneyId(value: string): boolean {
  return /^[A-Za-z0-9_.:-]{1,128}$/.test(value);
}

function isView(value: ReconciliationResponse): boolean {
  if (
    value.broker_rows_read !== 0 ||
    value.broker_read !== "absent" ||
    value.alpaca_called !== false ||
    value.reconciled !== false ||
    value.execution_permitted !== false ||
    value.order_submitted !== false ||
    value.order_route !== "absent" ||
    value.source !== "local_ledger" ||
    value.note.length === 0 ||
    value.local_orders !== value.rows.length ||
    value.local_fills > value.rows.length ||
    value.local_open > value.rows.length
  ) {
    return false;
  }
  return value.rows.every(
    (row) =>
      isMoneyId(row.client_order_id) &&
      (row.mode === "paper" || row.mode === "live") &&
      (row.side === "buy" || row.side === "sell") &&
      row.broker_status === "not_read" &&
      row.matched === false &&
      row.reason === "broker_not_read" &&
      row.broker_order_stored === (row.broker_order_id !== null),
  );
}

export function ReconciliationPage() {
  const [state, setState] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    document.title = "Reconciliation · Veytrix";
  }, []);

  useEffect(() => {
    let cancelled = false;
    apiGet<ReconciliationResponse>("/api/v1/ledger/reconciliation")
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setState(isView(payload) ? { status: "ready", payload } : { status: "unavailable" });
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

  const view = state.status === "ready" ? state.payload : null;

  return (
    <div className="vx-page">
      <div>
        <h1 className="vx-title">Reconciliation</h1>
        <p className="vx-lede">
          This page reads the local MAC-01 ledger. The broker account was not read, so a stored
          broker id is not a match.
        </p>
      </div>
      {state.status === "loading" ? <p className="text-sm text-muted">Loading the local ledger.</p> : null}
      {state.status === "unavailable" ? (
        <p className="vx-alert" role="alert">
          {UNAVAILABLE}
        </p>
      ) : null}
      {view ? (
        <>
          <dl className="grid max-w-xl gap-3 vx-card text-sm">
            <div className="flex justify-between gap-4">
              <dt>Broker read</dt>
              <dd className="font-mono">{view.broker_read}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>Reconciled</dt>
              <dd className="font-mono">{String(view.reconciled)}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>Alpaca called</dt>
              <dd className="font-mono">{String(view.alpaca_called)}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>Local orders</dt>
              <dd className="font-mono">{view.local_orders}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>Local fills</dt>
              <dd className="font-mono">{view.local_fills}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>Local open</dt>
              <dd className="font-mono">{view.local_open}</dd>
            </div>
          </dl>
          {view.rows.length === 0 ? (
            <p className="text-sm text-muted">No local orders. Nothing was invented.</p>
          ) : (
            <table className="w-full border-collapse text-sm">
              <caption className="sr-only">Local orders, broker side unread</caption>
              <thead>
                <tr className="border-b border-line text-left text-muted">
                  <th className="py-2 pr-4 font-medium">Client id</th>
                  <th className="py-2 pr-4 font-medium">Local status</th>
                  <th className="py-2 pr-4 font-medium">Broker status</th>
                  <th className="py-2 font-medium">Matched</th>
                </tr>
              </thead>
              <tbody>
                {view.rows.map((row) => (
                  <tr key={row.client_order_id} className="border-b border-line">
                    <td className="py-2 pr-4 font-mono">{row.client_order_id}</td>
                    <td className="py-2 pr-4 font-mono">{row.local_status}</td>
                    <td className="py-2 pr-4 font-mono">{row.broker_status}</td>
                    <td className="py-2 font-mono">{String(row.matched)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <p className="max-w-3xl text-sm text-muted">{view.note}</p>
        </>
      ) : null}
    </div>
  );
}
