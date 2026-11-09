import { useEffect, useState } from "react";
import { apiGet } from "../api/client";
import type { TreasuryMonthlySummary } from "../api/types";

const UNAVAILABLE = "Treasury summary is unavailable. No payout was invented.";
const MONEY = /^-?(?:0|[1-9]\d*)(?:\.\d+)?$/;

type LoadState =
  | { status: "loading" }
  | { status: "unavailable" }
  | { status: "ready"; summary: TreasuryMonthlySummary };

function isMoney(value: string, allowNegative: boolean): boolean {
  if (!MONEY.test(value)) {
    return false;
  }
  return allowNegative || !value.startsWith("-");
}

function isSummary(value: TreasuryMonthlySummary): boolean {
  return (
    value.source === "local_projection" &&
    value.period_closed === false &&
    value.distribution_fraction === "0.50" &&
    value.distribution_cap === "2000.00" &&
    value.review_day === 5 &&
    value.fees_included === false &&
    value.carryforward_stored === false &&
    value.broker_reconciled === false &&
    value.settled === false &&
    value.transfer_status === "not_attempted" &&
    value.approval_route === "absent" &&
    value.execution_permitted === false &&
    value.order_submitted === false &&
    value.transfer_submitted === false &&
    /^\d{4}-\d{2}$/.test(value.period) &&
    /^\d{4}-\d{2}-\d{2}$/.test(value.review_on) &&
    Number.isInteger(value.fills_counted) &&
    value.fills_counted >= 0 &&
    isMoney(value.realised_profit, true) &&
    isMoney(value.costs, false) &&
    isMoney(value.loss_carryforward, true) &&
    isMoney(value.eligible_profit, true) &&
    isMoney(value.proposed_distribution, false) &&
    isMoney(value.retained, false) &&
    isMoney(value.loss_carryforward_out, true) &&
    value.note.length > 0
  );
}

export function TreasuryPage() {
  const [summary, setSummary] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    document.title = "Treasury · Veytrix";
  }, []);

  useEffect(() => {
    let cancelled = false;
    apiGet<TreasuryMonthlySummary>("/api/v1/treasury/monthly-summary")
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setSummary(
          isSummary(payload) ? { status: "ready", summary: payload } : { status: "unavailable" },
        );
      })
      .catch(() => {
        if (!cancelled) {
          setSummary({ status: "unavailable" });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const ready = summary.status === "ready" ? summary.summary : null;

  return (
    <div className="vx-page">
      <div>
        <h1 className="vx-title">Treasury</h1>
        <p className="vx-lede">
          This page reads a local projection for the open month. It does not approve a payout
          and it does not send one.
        </p>
      </div>
      {summary.status === "loading" ? (
        <p className="text-sm text-muted">Loading the monthly projection.</p>
      ) : null}
      {summary.status === "unavailable" ? (
        <p className="vx-alert" role="alert">
          {UNAVAILABLE}
        </p>
      ) : null}
      {ready ? (
        <section aria-labelledby="monthly-summary" className="space-y-4">
          <h2 id="monthly-summary" className="vx-section-title">
            Monthly projection. Not a transfer. No payout is sent.
          </h2>
          <dl className="grid max-w-xl gap-3 vx-card text-sm">
            <div className="flex justify-between gap-4">
              <dt>Period</dt>
              <dd className="font-mono">{ready.period}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>Eligible profit</dt>
              <dd className="font-mono">{ready.eligible_profit}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>Proposed distribution</dt>
              <dd className="font-mono">{ready.proposed_distribution}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>Retained</dt>
              <dd className="font-mono">{ready.retained}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>Loss carryforward out</dt>
              <dd className="font-mono">{ready.loss_carryforward_out}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>Review date</dt>
              <dd className="font-mono">{ready.review_on}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>Paper fills counted</dt>
              <dd className="font-mono">{ready.fills_counted}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>Transfer submitted</dt>
              <dd className="font-mono">{String(ready.transfer_submitted)}</dd>
            </div>
          </dl>
          <p className="max-w-3xl text-sm text-muted">{ready.note}</p>
        </section>
      ) : null}
    </div>
  );
}
