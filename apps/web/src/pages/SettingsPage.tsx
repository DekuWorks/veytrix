import { useEffect, useState } from "react";
import { apiGet } from "../api/client";
import type { DiagnosticsResponse } from "../api/types";

const UNAVAILABLE = "Settings are unavailable. No live switch was invented.";

type LoadState =
  | { status: "loading" }
  | { status: "unavailable" }
  | { status: "ready"; payload: DiagnosticsResponse };

function isDiagnostics(value: DiagnosticsResponse): boolean {
  return (
    value.service === "veytrix-api" &&
    value.env === "local" &&
    value.trading_mode === "paper" &&
    value.live_broker === "disabled" &&
    value.auth === "not_configured" &&
    value.sample_data === true &&
    value.execution_permitted === false &&
    value.daily_weekly_stops_enforced === false &&
    value.rate_limit === "process_local" &&
    value.csrf === "not_implemented" &&
    value.versions.api === "0.1.0" &&
    value.versions.python.length > 0
  );
}

export function SettingsPage() {
  const [state, setState] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    document.title = "Settings · Veytrix";
  }, []);

  useEffect(() => {
    let cancelled = false;
    apiGet<DiagnosticsResponse>("/api/v1/diagnostics")
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setState(isDiagnostics(payload) ? { status: "ready", payload } : { status: "unavailable" });
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
    <div className="vx-page">
      <div>
        <h1 className="vx-title">Settings</h1>
        <p className="vx-lede">
          This page reads the local diagnostics. There is no field to edit, no key to paste, and
          no switch that turns on live trading.
        </p>
      </div>
      {state.status === "loading" ? <p className="text-sm text-muted">Loading settings.</p> : null}
      {state.status === "unavailable" ? (
        <p className="vx-alert" role="alert">
          {UNAVAILABLE}
        </p>
      ) : null}
      {ready ? (
        <section aria-labelledby="local-settings" className="space-y-4">
          <h2 id="local-settings" className="vx-section-title">
            Fixed local posture. Nothing on this page can be saved.
          </h2>
          <dl className="grid max-w-xl gap-3 vx-card text-sm">
            <div className="flex justify-between gap-4">
              <dt>Environment</dt>
              <dd className="font-mono">{ready.env}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>Trading mode</dt>
              <dd className="font-mono">{ready.trading_mode}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>Live broker</dt>
              <dd className="font-mono">{ready.live_broker}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>Authentication</dt>
              <dd className="font-mono">{ready.auth}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>CSRF</dt>
              <dd className="font-mono">{ready.csrf}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>Rate limit</dt>
              <dd className="font-mono">{ready.rate_limit}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>Stops enforced</dt>
              <dd className="font-mono">{String(ready.daily_weekly_stops_enforced)}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>Execution permitted</dt>
              <dd className="font-mono">{String(ready.execution_permitted)}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>API version</dt>
              <dd className="font-mono">{ready.versions.api}</dd>
            </div>
          </dl>
        </section>
      ) : null}
    </div>
  );
}
