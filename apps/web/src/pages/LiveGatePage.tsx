import { useEffect, useState } from "react";
import { apiGet } from "../api/client";
import type { SubmissionEvidenceResponse } from "../api/types";

const UNAVAILABLE = "Live-gate evidence is unavailable. Nothing was submitted.";

const NAMES = [
  "mode_live",
  "live_enabled",
  "submit_orders",
  "confirm_phrase",
  "submit_flag",
  "account_match",
  "account_active",
  "kill_switch_off",
] as const;

const NEVER_MET = new Set(["submit_flag", "account_match", "account_active", "kill_switch_off"]);

type LoadState =
  | { status: "loading" }
  | { status: "unavailable" }
  | { status: "ready"; payload: SubmissionEvidenceResponse };

function isEvidence(value: SubmissionEvidenceResponse): boolean {
  if (
    value.account_status !== "not_read" ||
    value.ledger_kill_switch !== "not_read" ||
    value.submit_flag !== false ||
    value.api_reaches_engine !== false ||
    value.broker_called !== false ||
    value.paper_submission_from_api !== false ||
    value.live_submission_possible !== false ||
    value.expected_account_echoed !== false ||
    value.confirm_phrase_echoed !== false ||
    value.execution_permitted !== false ||
    value.order_submitted !== false ||
    value.order_route !== "absent" ||
    value.source !== "local_config" ||
    value.note.length === 0 ||
    value.conditions.length !== NAMES.length
  ) {
    return false;
  }
  const met = value.conditions.reduce((count, item) => count + (item.met ? 1 : 0), 0);
  return (
    value.conditions_met === met &&
    value.conditions.every(
      (item, index) => item.name === NAMES[index] && !(NEVER_MET.has(item.name) && item.met),
    )
  );
}

function flag(value: boolean | null): string {
  if (value === null) {
    return "unknown";
  }
  return value ? "true" : "false";
}

export function LiveGatePage() {
  const [state, setState] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    document.title = "Live gate · Veytrix";
  }, []);

  useEffect(() => {
    let cancelled = false;
    apiGet<SubmissionEvidenceResponse>("/api/v1/system/submission")
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setState(isEvidence(payload) ? { status: "ready", payload } : { status: "unavailable" });
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

  const evidence = state.status === "ready" ? state.payload : null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Live gate</h1>
        <p className="mt-2 max-w-3xl text-sm text-muted">
          Eight conditions have to hold before the MAC-01 CLI can send a live order. This page
          only reads the local config. It cannot turn a condition on.
        </p>
      </div>
      {state.status === "loading" ? <p className="text-sm text-muted">Loading live-gate evidence.</p> : null}
      {state.status === "unavailable" ? (
        <p className="text-sm text-danger" role="alert">
          {UNAVAILABLE}
        </p>
      ) : null}
      {evidence ? (
        <>
          <dl className="grid max-w-xl gap-3 rounded-md border border-line bg-panel p-4 text-sm">
            <div className="flex justify-between gap-4">
              <dt>Live submission from this API</dt>
              <dd className="font-mono">{String(evidence.live_submission_possible)}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>Paper submission from this API</dt>
              <dd className="font-mono">{String(evidence.paper_submission_from_api)}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>API reaches the engine</dt>
              <dd className="font-mono">{String(evidence.api_reaches_engine)}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>Broker called</dt>
              <dd className="font-mono">{String(evidence.broker_called)}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>Account</dt>
              <dd className="font-mono">{evidence.account_status}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>Config mode</dt>
              <dd className="font-mono">{evidence.config_mode ?? "unknown"}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>Config submit orders</dt>
              <dd className="font-mono">{flag(evidence.config_submit_orders)}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>Expected account set</dt>
              <dd className="font-mono">{flag(evidence.expected_account_set)}</dd>
            </div>
          </dl>
          <table className="w-full max-w-xl border-collapse text-sm">
            <caption className="sr-only">Live-gate conditions</caption>
            <thead>
              <tr className="border-b border-line text-left text-muted">
                <th className="py-2 pr-4 font-medium">Condition</th>
                <th className="py-2 font-medium">Met</th>
              </tr>
            </thead>
            <tbody>
              {evidence.conditions.map((item) => (
                <tr key={item.name} className="border-b border-line">
                  <td className="py-2 pr-4 font-mono">{item.name}</td>
                  <td className="py-2 font-mono">{String(item.met)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="max-w-3xl text-sm text-muted">{evidence.note}</p>
        </>
      ) : null}
    </div>
  );
}
