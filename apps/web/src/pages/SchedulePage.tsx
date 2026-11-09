import { useEffect, useState } from "react";
import { apiGet } from "../api/client";
import type { Mac01ScheduleResponse } from "../api/types";

const UNAVAILABLE = "Scheduler status is unavailable. No run was started.";

type LoadState =
  | { status: "loading" }
  | { status: "unavailable" }
  | { status: "ready"; payload: Mac01ScheduleResponse };

function isSchedule(value: Mac01ScheduleResponse): boolean {
  return (
    value.strategy === "mac-01" &&
    value.timezone === "America/New_York" &&
    value.run_clock === "09:35" &&
    value.delay_after_open_minutes === 5 &&
    value.calendar === "not_read" &&
    value.next_session === "unknown" &&
    value.running === false &&
    value.process === "absent" &&
    value.submit_flag === false &&
    value.can_start === false &&
    value.alpaca_called === false &&
    value.execution_permitted === false &&
    value.order_submitted === false &&
    value.order_route === "absent" &&
    value.source === "local_config" &&
    value.note.length > 0
  );
}

function flag(value: boolean | null): string {
  if (value === null) {
    return "unknown";
  }
  return value ? "true" : "false";
}

export function SchedulePage() {
  const [state, setState] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    document.title = "Scheduler · Veytrix";
  }, []);

  useEffect(() => {
    let cancelled = false;
    apiGet<Mac01ScheduleResponse>("/api/v1/strategies/mac-01/schedule")
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setState(isSchedule(payload) ? { status: "ready", payload } : { status: "unavailable" });
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

  const schedule = state.status === "ready" ? state.payload : null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Scheduler</h1>
        <p className="mt-2 max-w-3xl text-sm text-muted">
          MAC-01 is published for 09:35 America/New_York, five minutes after the open. This page
          does not read the exchange calendar and cannot start a run.
        </p>
      </div>
      {state.status === "loading" ? <p className="text-sm text-muted">Loading scheduler status.</p> : null}
      {state.status === "unavailable" ? (
        <p className="text-sm text-danger" role="alert">
          {UNAVAILABLE}
        </p>
      ) : null}
      {schedule ? (
        <dl className="grid max-w-xl gap-3 rounded-md border border-line bg-panel p-4 text-sm">
          <div className="flex justify-between gap-4">
            <dt>Clock</dt>
            <dd className="font-mono">
              {schedule.run_clock} {schedule.timezone}
            </dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt>Calendar</dt>
            <dd className="font-mono">{schedule.calendar}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt>Next session</dt>
            <dd className="font-mono">{schedule.next_session}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt>Running</dt>
            <dd className="font-mono">{String(schedule.running)}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt>Process</dt>
            <dd className="font-mono">{schedule.process}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt>Submit flag</dt>
            <dd className="font-mono">{String(schedule.submit_flag)}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt>Can start</dt>
            <dd className="font-mono">{String(schedule.can_start)}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt>Config submit orders</dt>
            <dd className="font-mono">{flag(schedule.config_submit_orders)}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt>Alpaca called</dt>
            <dd className="font-mono">{String(schedule.alpaca_called)}</dd>
          </div>
        </dl>
      ) : null}
      {schedule ? <p className="max-w-3xl text-sm text-muted">{schedule.note}</p> : null}
    </div>
  );
}
