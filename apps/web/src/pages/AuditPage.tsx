import { useEffect, useState } from "react";
import { apiGet } from "../api/client";
import {
  COINBASE_PRODUCTS,
  type AuditLogEntry,
  type AuditLogListResponse,
  type DiagnosticsResponse,
  type PaperSizeJournalEntry,
  type PaperSizeJournalListResponse,
} from "../api/types";

const JOURNAL_HEADER = "Paper size journal on this machine. No order is sent.";
const JOURNAL_EMPTY = "No paper sizes recorded yet.";
const JOURNAL_UNAVAILABLE = "Paper size journal is unavailable. No size was invented.";
const LOG_HEADER = "Local audit log. No order is sent.";
const LOG_EMPTY = "No audit events recorded yet.";
const LOG_UNAVAILABLE = "Audit log is unavailable. No event was invented.";
const BINDING = ["risk", "allocation", "both", "none"] as const;
const CORRELATION_ID = /^[A-Za-z0-9_-]{1,64}$/;

type Probe =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; payload: DiagnosticsResponse };

function isDiagnostics(value: unknown): value is DiagnosticsResponse {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const record = value as Record<string, unknown>;
  return (
    record.env === "local" &&
    record.trading_mode === "paper" &&
    record.live_broker === "disabled" &&
    record.auth === "not_configured" &&
    record.execution_permitted === false &&
    record.daily_weekly_stops_enforced === false &&
    typeof record.sample_data === "boolean"
  );
}

function sampleSeriesLine(sampleData: boolean): string {
  return sampleData ? "Sample series present" : "Sample series absent";
}

function isJournalEntry(value: PaperSizeJournalEntry): boolean {
  const record = value as PaperSizeJournalEntry & Record<string, unknown>;
  return (
    (COINBASE_PRODUCTS as readonly string[]).includes(value.symbol) &&
    Number.isInteger(value.shares) &&
    value.shares >= 0 &&
    (BINDING as readonly string[]).includes(value.binding_constraint) &&
    value.planned_risk.trim().length > 0 &&
    value.recorded_at.includes("T") &&
    value.execution_permitted === false &&
    value.order_submitted === false &&
    !("order_id" in record) &&
    !("broker_id" in record) &&
    !("fill" in record)
  );
}

type JournalState =
  | { status: "loading" }
  | { status: "unavailable" }
  | { status: "ready"; entries: PaperSizeJournalEntry[] };

function isAuditEntry(value: AuditLogEntry): boolean {
  const record = value as AuditLogEntry & Record<string, unknown>;
  return (
    value.action === "risk.size.recorded" &&
    (COINBASE_PRODUCTS as readonly string[]).includes(value.symbol) &&
    Number.isInteger(value.shares) &&
    value.shares >= 0 &&
    (BINDING as readonly string[]).includes(value.binding_constraint) &&
    CORRELATION_ID.test(value.correlation_id) &&
    value.created_at.includes("T") &&
    value.execution_permitted === false &&
    value.order_submitted === false &&
    !("order_id" in record) &&
    !("broker_id" in record) &&
    !("payload" in record)
  );
}

function isAuditLog(value: AuditLogListResponse): boolean {
  return (
    value.source === "local_audit_log" &&
    value.execution_permitted === false &&
    value.order_submitted === false &&
    Array.isArray(value.events) &&
    value.events.every(isAuditEntry)
  );
}

type LogState =
  | { status: "loading" }
  | { status: "unavailable" }
  | { status: "ready"; events: AuditLogEntry[] };

export function AuditPage() {
  const [probe, setProbe] = useState<Probe>({ status: "loading" });
  const [journal, setJournal] = useState<JournalState>({ status: "loading" });
  const [log, setLog] = useState<LogState>({ status: "loading" });

  useEffect(() => {
    document.title = "Audit · Veytrix";
  }, []);

  useEffect(() => {
    let cancelled = false;
    apiGet<DiagnosticsResponse>("/api/v1/diagnostics")
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setProbe(isDiagnostics(payload) ? { status: "ready", payload } : { status: "error" });
      })
      .catch(() => {
        if (!cancelled) {
          setProbe({ status: "error" });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    apiGet<PaperSizeJournalListResponse>("/api/v1/audit/size-journal")
      .then((payload) => {
        if (cancelled) {
          return;
        }
        if (!Array.isArray(payload.entries) || !payload.entries.every(isJournalEntry)) {
          setJournal({ status: "unavailable" });
          return;
        }
        setJournal({ status: "ready", entries: payload.entries });
      })
      .catch(() => {
        if (!cancelled) {
          setJournal({ status: "unavailable" });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    apiGet<AuditLogListResponse>("/api/v1/audit/log")
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setLog(isAuditLog(payload) ? { status: "ready", events: payload.events } : { status: "unavailable" });
      })
      .catch(() => {
        if (!cancelled) {
          setLog({ status: "unavailable" });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const ready = probe.status === "ready" ? probe.payload : null;

  return (
    <div className="vx-page">
      <div>
        <h1 className="vx-title">Audit</h1>
        <p className="vx-lede">
          This page reads the local diagnostics probe. It does not size a position. No order is
          sent.
        </p>
      </div>
      {probe.status === "loading" ? <p className="text-sm text-muted">Checking diagnostics.</p> : null}
      {probe.status === "error" ? (
        <p className="vx-alert" role="alert">
          Diagnostics probe failed. No status was invented.
        </p>
      ) : null}
      {ready ? (
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
            <dt>Execution permitted</dt>
            <dd className="font-mono">{String(ready.execution_permitted)}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt>Stops enforced</dt>
            <dd className="font-mono">{String(ready.daily_weekly_stops_enforced)}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt>Sample series</dt>
            <dd>{sampleSeriesLine(ready.sample_data)}</dd>
          </div>
        </dl>
      ) : null}
      <section aria-labelledby="size-journal" className="space-y-4">
        <h2 id="size-journal" className="vx-section-title">
          {JOURNAL_HEADER}
        </h2>
        {journal.status === "loading" ? (
          <p className="text-sm text-muted">Loading paper sizes.</p>
        ) : null}
        {journal.status === "unavailable" ? (
          <p className="vx-alert" role="alert">
            {JOURNAL_UNAVAILABLE}
          </p>
        ) : null}
        {journal.status === "ready" && journal.entries.length === 0 ? (
          <p className="text-sm text-muted">{JOURNAL_EMPTY}</p>
        ) : null}
        {journal.status === "ready" && journal.entries.length > 0 ? (
          <ul className="grid max-w-xl gap-3">
            {journal.entries.map((item) => (
              <li key={item.id} className="vx-card text-sm">
                <h3 className="text-base font-semibold">{item.symbol}</h3>
                <p className="mt-2">Shares {item.shares}</p>
                <p className="mt-2">Binding constraint {item.binding_constraint}</p>
                <p className="mt-2">Planned risk {item.planned_risk}</p>
                <p className="mt-2">Recorded at {item.recorded_at}.</p>
              </li>
            ))}
          </ul>
        ) : null}
      </section>
      <section aria-labelledby="audit-log" className="space-y-4">
        <h2 id="audit-log" className="vx-section-title">
          {LOG_HEADER}
        </h2>
        {log.status === "loading" ? <p className="text-sm text-muted">Loading the audit log.</p> : null}
        {log.status === "unavailable" ? (
          <p className="vx-alert" role="alert">
            {LOG_UNAVAILABLE}
          </p>
        ) : null}
        {log.status === "ready" && log.events.length === 0 ? (
          <p className="text-sm text-muted">{LOG_EMPTY}</p>
        ) : null}
        {log.status === "ready" && log.events.length > 0 ? (
          <ul className="grid max-w-xl gap-3">
            {log.events.map((item) => (
              <li key={item.id} className="vx-card text-sm">
                <h3 className="text-base font-semibold">{item.symbol}</h3>
                <p className="mt-2">Action {item.action}</p>
                <p className="mt-2">Shares {item.shares}</p>
                <p className="mt-2">Binding constraint {item.binding_constraint}</p>
                <p className="mt-2">Order submitted false</p>
                <p className="mt-2">Recorded at {item.created_at}.</p>
              </li>
            ))}
          </ul>
        ) : null}
      </section>
    </div>
  );
}
