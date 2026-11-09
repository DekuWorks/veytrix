import { useEffect, useState } from "react";
import { apiGet } from "../api/client";
import type { FuturesPostureResponse } from "../api/types";

const UNAVAILABLE = "Futures posture is unavailable. No order was sent.";

type LoadState =
  | { status: "loading" }
  | { status: "unavailable" }
  | { status: "ready"; payload: FuturesPostureResponse };

function isPosture(value: FuturesPostureResponse): boolean {
  return (
    value.desk === "FUTURES-01" &&
    value.status === "disabled" &&
    value.symbols.length === 2 &&
    value.symbols[0] === "MES" &&
    value.symbols[1] === "MNQ" &&
    value.topstep_automation === "disabled" &&
    value.topstep_account === "not_connected" &&
    value.orders === "absent" &&
    value.market_data === "not_read" &&
    value.can_enable === false &&
    value.execution_permitted === false &&
    value.order_submitted === false &&
    value.broker_called === false &&
    value.source === "local_posture" &&
    value.note.length > 0
  );
}

export function FuturesPage() {
  const [state, setState] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    document.title = "Futures · Veytrix";
  }, []);

  useEffect(() => {
    let cancelled = false;
    apiGet<FuturesPostureResponse>("/api/v1/futures/posture")
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setState(isPosture(payload) ? { status: "ready", payload } : { status: "unavailable" });
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
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold">Futures · FUTURES-01</h1>
        <p className="max-w-3xl text-sm text-muted">
          MES and MNQ are research labels. Topstep automation stays off. No order is sent.
        </p>
      </header>
      {state.status === "loading" ? <p className="text-sm text-muted">Loading the futures posture.</p> : null}
      {state.status === "unavailable" ? (
        <p className="text-sm text-danger" role="alert">
          {UNAVAILABLE}
        </p>
      ) : null}
      {ready ? (
        <dl className="grid max-w-xl gap-3 text-sm">
          <div className="flex justify-between gap-4">
            <dt>Desk</dt>
            <dd className="font-mono">{ready.desk}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt>Status</dt>
            <dd className="font-mono">{ready.status}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt>Symbols</dt>
            <dd className="font-mono">{ready.symbols.join(", ")}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt>Topstep automation</dt>
            <dd className="font-mono">{ready.topstep_automation}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt>Topstep account</dt>
            <dd className="font-mono">{ready.topstep_account}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt>Orders</dt>
            <dd className="font-mono">{ready.orders}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt>Market data</dt>
            <dd className="font-mono">{ready.market_data}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt>Can enable</dt>
            <dd className="font-mono">false</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt>Execution permitted</dt>
            <dd className="font-mono">false</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt>Order submitted</dt>
            <dd className="font-mono">false</dd>
          </div>
        </dl>
      ) : null}
    </div>
  );
}
