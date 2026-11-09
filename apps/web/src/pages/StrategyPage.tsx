import { useCallback, useEffect, useState } from "react";
import { ApiError, apiGet, apiPost, errorDetail } from "../api/client";
import type {
  Mac01ChartResponse,
  Mac01OrderListResponse,
  Mac01PerformanceResponse,
  Mac01SignalListResponse,
  Mac01StatusResponse,
} from "../api/types";
import { KpiCard } from "../components/KpiCard";
import { StrategyChart } from "../components/StrategyChart";
import { STRATEGY_NOTICE } from "../content";

const BASE = "/api/v1/strategies/mac-01";
const REFRESH_MS = 30_000;

type Loaded = {
  status: Mac01StatusResponse;
  signals: Mac01SignalListResponse;
  orders: Mac01OrderListResponse;
  performance: Mac01PerformanceResponse;
  chart: Mac01ChartResponse;
};

type PageState = { status: "loading" } | { status: "unavailable"; detail: string } | { status: "ready"; data: Loaded };

function yesNo(value: boolean | null): string {
  if (value === null) {
    return "unknown";
  }
  return value ? "yes" : "no";
}

function money(value: string | null, available: boolean): string {
  return available && value !== null ? `$${value}` : "Unavailable";
}

function modeLabel(mode: "paper" | "live" | null): string {
  if (mode === "live") {
    return "LIVE · real money";
  }
  if (mode === "paper") {
    return "Paper · paper money";
  }
  return "Unknown · config invalid";
}

function sizeText(order: Mac01OrderListResponse["orders"][number]): string {
  if (order.side === "buy" && order.notional !== null) {
    return `$${order.notional} notional`;
  }
  return order.qty !== null ? `${order.qty} shares (full position)` : "unknown";
}

export function StrategyPage() {
  const [state, setState] = useState<PageState>({ status: "loading" });
  const [confirmKill, setConfirmKill] = useState(false);
  const [pending, setPending] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    document.title = "Strategy · Veytrix";
  }, []);

  const load = useCallback(async () => {
    try {
      const [status, signals, orders, performance, chart] = await Promise.all([
        apiGet<Mac01StatusResponse>(`${BASE}/status`),
        apiGet<Mac01SignalListResponse>(`${BASE}/signals`),
        apiGet<Mac01OrderListResponse>(`${BASE}/orders`),
        apiGet<Mac01PerformanceResponse>(`${BASE}/performance`),
        apiGet<Mac01ChartResponse>(`${BASE}/chart`),
      ]);
      setState({ status: "ready", data: { status, signals, orders, performance, chart } });
    } catch (error) {
      const detail = error instanceof ApiError ? errorDetail(error.body) : null;
      setState({ status: "unavailable", detail: detail ?? "The MAC-01 API is not reachable." });
    }
  }, []);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [load]);

  async function control(action: "pause" | "resume" | "kill-switch") {
    setPending(true);
    setActionError(null);
    try {
      await apiPost<Mac01StatusResponse>(`${BASE}/${action}`, {});
      setConfirmKill(false);
      await load();
    } catch (error) {
      const detail = error instanceof ApiError ? errorDetail(error.body) : null;
      setActionError(detail ?? "The control request failed. Nothing changed.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold">Strategy · MAC-01</h1>
        <p className="text-sm text-muted">AAPL daily SMA 20/50 crossover. Long only, at most $100.</p>
        <p className="text-sm text-warn">{STRATEGY_NOTICE}</p>
      </header>

      {state.status === "loading" ? <p className="text-sm text-muted">Loading MAC-01 status.</p> : null}
      {state.status === "unavailable" ? (
        <p role="alert" className="text-sm text-warn">
          {state.detail}
        </p>
      ) : null}

      {state.status === "ready" ? (
        <StrategyBody
          data={state.data}
          confirmKill={confirmKill}
          pending={pending}
          actionError={actionError}
          onPause={() => void control("pause")}
          onResume={() => void control("resume")}
          onKillRequest={() => setConfirmKill(true)}
          onKillCancel={() => setConfirmKill(false)}
          onKillConfirm={() => void control("kill-switch")}
        />
      ) : null}
    </div>
  );
}

type BodyProps = {
  data: Loaded;
  confirmKill: boolean;
  pending: boolean;
  actionError: string | null;
  onPause: () => void;
  onResume: () => void;
  onKillRequest: () => void;
  onKillCancel: () => void;
  onKillConfirm: () => void;
};

function StrategyBody({
  data,
  confirmKill,
  pending,
  actionError,
  onPause,
  onResume,
  onKillRequest,
  onKillCancel,
  onKillConfirm,
}: BodyProps) {
  const { status, signals, orders, performance, chart } = data;
  const live = status.config_mode === "live";

  return (
    <>
      <p
        role="status"
        className={`rounded-md border p-3 text-sm ${live ? "border-warn text-warn" : "border-line text-muted"}`}
      >
        Mode: {modeLabel(status.config_mode)}. Orders are placed only by the scheduled runner on this
        machine. There is no buy or sell button.
      </p>

      <section aria-labelledby="health" className="space-y-3">
        <h2 id="health" className="text-lg font-semibold">
          Health
        </h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <KpiCard
            label="Last run"
            value={status.last_run_status ?? "never"}
            detail={status.last_run_at ?? "No runner pass yet."}
            note={status.last_run_message ?? undefined}
          />
          <KpiCard
            label="Signal session"
            value={status.last_session_date ?? "none"}
            detail={`Strategy ${status.strategy_version ?? "unknown"}. Last mode ${status.last_mode ?? "none"}.`}
          />
          <KpiCard
            label="Controls"
            value={status.kill_switch ? "Kill switch on" : status.paused ? "Paused" : "Running"}
            detail={`Paused ${yesNo(status.paused)}. Config kill switch ${yesNo(status.config_kill_switch)}.`}
          />
          <KpiCard
            label="Caps"
            value={status.max_notional_per_trade !== null ? `$${status.max_notional_per_trade}` : "unknown"}
            detail={`Position cap $${status.max_position_notional ?? "?"}. ${status.max_orders_per_day ?? "?"} orders a day.`}
          />
        </div>
        <ul className="grid gap-1 text-sm text-muted sm:grid-cols-2">
          <li>Config valid: {yesNo(status.config_valid)}</li>
          <li>Submit orders in config: {yesNo(status.config_submit_orders)}</li>
          <li>Live enabled in config: {yesNo(status.config_live_enabled)}</li>
          <li>Expected account number set: {yesNo(status.config_expected_account_set)}</li>
        </ul>
      </section>

      <section aria-labelledby="controls" className="space-y-3">
        <h2 id="controls" className="text-lg font-semibold">
          Controls
        </h2>
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            className="rounded-md border border-line px-3 py-2 text-sm"
            disabled={pending || status.paused}
            onClick={onPause}
          >
            Pause
          </button>
          <button
            type="button"
            className="rounded-md border border-line px-3 py-2 text-sm"
            disabled={pending || !status.paused}
            onClick={onResume}
          >
            Resume
          </button>
          {!confirmKill ? (
            <button
              type="button"
              className="rounded-md border border-warn px-3 py-2 text-sm text-warn"
              disabled={pending || status.kill_switch}
              onClick={onKillRequest}
            >
              Engage kill switch
            </button>
          ) : (
            <>
              <button
                type="button"
                className="rounded-md border border-warn bg-panel-2 px-3 py-2 text-sm text-warn"
                disabled={pending}
                onClick={onKillConfirm}
              >
                Confirm: block every MAC-01 order
              </button>
              <button
                type="button"
                className="rounded-md border border-line px-3 py-2 text-sm"
                disabled={pending}
                onClick={onKillCancel}
              >
                Cancel
              </button>
            </>
          )}
        </div>
        <p className="text-sm text-muted">
          Releasing the kill switch needs the command line on this machine. These controls do not cancel an
          order that is already at Alpaca.
        </p>
        {actionError !== null ? (
          <p role="alert" className="text-sm text-warn">
            {actionError}
          </p>
        ) : null}
      </section>

      <section aria-labelledby="chart" className="space-y-3">
        <h2 id="chart" className="text-lg font-semibold">
          Chart
        </h2>
        {chart.available ? (
          <StrategyChart
            chart={chart}
            caption={`Adjusted daily closes from ${chart.source ?? "unknown"}, as of ${chart.as_of ?? "unknown"}.`}
          />
        ) : (
          <p className="text-sm text-muted">{chart.note}</p>
        )}
      </section>

      <section aria-labelledby="performance" className="space-y-3">
        <h2 id="performance" className="text-lg font-semibold">
          Performance ({performance.mode})
        </h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <KpiCard
            label="Realised P&L"
            value={money(performance.realised_pl, performance.realised_available)}
            detail={`${performance.filled_orders} filled order(s). Before fees.`}
          />
          <KpiCard
            label="Unrealised P&L"
            value={money(performance.unrealised_pl, performance.unrealised_available)}
            detail={
              performance.position_qty !== null
                ? `${performance.position_qty} shares as of ${performance.position_as_of ?? "unknown"}.`
                : "No position snapshot in this mode."
            }
          />
        </div>
        <p className="text-sm text-muted">{performance.note}</p>
      </section>

      <section aria-labelledby="signals" className="space-y-3">
        <h2 id="signals" className="text-lg font-semibold">
          Signals
        </h2>
        {signals.signals.length === 0 ? (
          <p className="text-sm text-muted">No signals recorded yet.</p>
        ) : (
          <div className="overflow-x-auto rounded-md border border-line">
            <table className="w-full text-left text-sm">
              <caption className="sr-only">MAC-01 signals, newest first</caption>
              <thead className="bg-panel-2">
                <tr>
                  <th scope="col" className="px-3 py-2 font-medium">Session</th>
                  <th scope="col" className="px-3 py-2 font-medium">Signal</th>
                  <th scope="col" className="px-3 py-2 font-medium">Close</th>
                  <th scope="col" className="px-3 py-2 font-medium">SMA fast / slow</th>
                  <th scope="col" className="px-3 py-2 font-medium">Decision</th>
                </tr>
              </thead>
              <tbody>
                {signals.signals.map((signal) => (
                  <tr key={`${signal.strategy_version}-${signal.session_date}`} className="border-t border-line">
                    <td className="px-3 py-2 font-mono">{signal.session_date}</td>
                    <td className="px-3 py-2">{signal.side}</td>
                    <td className="px-3 py-2 font-mono">{signal.close}</td>
                    <td className="px-3 py-2 font-mono">
                      {signal.fast_cur} / {signal.slow_cur}
                    </td>
                    <td className="px-3 py-2">
                      {signal.decision}: {signal.decision_reason}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section aria-labelledby="orders" className="space-y-3">
        <h2 id="orders" className="text-lg font-semibold">
          Orders
        </h2>
        {orders.orders.length === 0 ? (
          <p className="text-sm text-muted">No orders recorded.</p>
        ) : (
          <div className="overflow-x-auto rounded-md border border-line">
            <table className="w-full text-left text-sm">
              <caption className="sr-only">MAC-01 orders, newest first</caption>
              <thead className="bg-panel-2">
                <tr>
                  <th scope="col" className="px-3 py-2 font-medium">Session</th>
                  <th scope="col" className="px-3 py-2 font-medium">Mode</th>
                  <th scope="col" className="px-3 py-2 font-medium">Side</th>
                  <th scope="col" className="px-3 py-2 font-medium">Size</th>
                  <th scope="col" className="px-3 py-2 font-medium">Status</th>
                  <th scope="col" className="px-3 py-2 font-medium">Filled</th>
                </tr>
              </thead>
              <tbody>
                {orders.orders.map((order) => (
                  <tr key={order.client_order_id} className="border-t border-line">
                    <td className="px-3 py-2 font-mono">{order.session_date}</td>
                    <td className="px-3 py-2">{order.mode}</td>
                    <td className="px-3 py-2">{order.side}</td>
                    <td className="px-3 py-2 font-mono">{sizeText(order)}</td>
                    <td className="px-3 py-2">{order.status}</td>
                    <td className="px-3 py-2 font-mono">
                      {order.filled_qty}
                      {order.filled_avg_price !== null ? ` at $${order.filled_avg_price}` : ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
