import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiGet, apiPost } from "../api/client";
import type {
  Mac01ChartResponse,
  Mac01OrderListResponse,
  Mac01PerformanceResponse,
  Mac01SignalListResponse,
  Mac01StatusResponse,
} from "../api/types";
import { AppRoutes } from "../App";
import { STRATEGY_NOTICE } from "../content";

const { createChart, setData, createSeriesMarkers } = vi.hoisted(() => {
  const setData = vi.fn();
  const createSeriesMarkers = vi.fn();
  const createChart = vi.fn(() => ({
    addSeries: vi.fn(() => ({ setData })),
    remove: vi.fn(),
    timeScale: () => ({ fitContent: vi.fn() }),
  }));
  return { createChart, setData, createSeriesMarkers };
});

vi.mock("lightweight-charts", () => ({
  LineSeries: { type: "Line" },
  ColorType: { Solid: "solid" },
  createChart,
  createSeriesMarkers,
}));

vi.mock("../api/client", () => ({
  ApiError: class ApiError extends Error {
    readonly status: number;
    readonly body: unknown;
    constructor(status: number, body: unknown) {
      super("API request failed");
      this.status = status;
      this.body = body;
    }
  },
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  errorDetail: (body: unknown) =>
    typeof body === "object" && body !== null && "detail" in body && typeof body.detail === "string"
      ? body.detail
      : null,
}));

const status: Mac01StatusResponse = {
  strategy: "mac-01",
  strategy_version: "mac-01.3",
  symbol: "AAPL",
  broker: "alpaca_trading_api",
  order_route: "none",
  order_submitter: "cli_runner_only",
  config_valid: true,
  config_mode: "paper",
  money: "paper",
  config_live_enabled: false,
  config_expected_account_set: false,
  config_submit_orders: false,
  config_kill_switch: false,
  max_notional_per_trade: "100.00",
  max_position_notional: "100.00",
  max_orders_per_day: 2,
  last_mode: "paper",
  paused: false,
  kill_switch: false,
  last_run_at: "2026-11-09T14:35:02Z",
  last_run_status: "ok",
  last_run_message: "DRY_RUN: would submit buy $100.00 notional AAPL market DAY (paper)",
  last_session_date: "2026-11-06",
  disclaimer: "Not investment advice.",
};

const signals: Mac01SignalListResponse = {
  signals: [
    {
      session_date: "2026-11-06",
      strategy_version: "mac-01.3",
      symbol: "AAPL",
      side: "BUY",
      reason: "fast crossed above slow",
      close: "110",
      fast_prev: "100",
      slow_prev: "100",
      fast_cur: "100.5",
      slow_cur: "100.2",
      decision: "DRY_RUN",
      decision_reason: "would submit",
      inputs_hash: "abc",
      created_at: "2026-11-09T14:35:01Z",
      decided_at: "2026-11-09T14:35:02Z",
    },
  ],
};

const orders: Mac01OrderListResponse = {
  orders: [
    {
      client_order_id: "mac01-paper-1",
      mode: "paper",
      session_date: "2026-11-06",
      side: "buy",
      notional: "100.00",
      qty: null,
      order_type: "market",
      time_in_force: "day",
      status: "filled",
      broker_order_id: "b-1",
      filled_qty: "0.904977375",
      filled_avg_price: "110.50",
      submitted_at: "2026-11-09T14:35:02Z",
      created_at: "2026-11-09T14:35:02Z",
      updated_at: "2026-11-09T14:35:03Z",
      last_error: null,
    },
  ],
};

const performance: Mac01PerformanceResponse = {
  mode: "paper",
  realised_pl: "0",
  realised_available: true,
  unrealised_pl: null,
  unrealised_available: false,
  position_qty: null,
  avg_entry_price: null,
  market_price: null,
  position_as_of: null,
  filled_orders: 1,
  note: "Realised P&L uses broker-reported fills.",
};

const chart: Mac01ChartResponse = {
  available: true,
  symbol: "AAPL",
  source: "alpaca-iex-adjusted",
  as_of: "2026-11-09T14:35:01Z",
  fast_period: 20,
  slow_period: 50,
  points: [
    { session_date: "2026-11-05", close: "100", sma_fast: "100", sma_slow: "100" },
    { session_date: "2026-11-06", close: "110", sma_fast: "100.5", sma_slow: "100.2" },
  ],
  markers: [{ session_date: "2026-11-06", side: "BUY" }],
  note: "Adjusted daily closes.",
};

function mockApi(overrides: Partial<{ status: Mac01StatusResponse; chart: Mac01ChartResponse }> = {}) {
  vi.mocked(apiGet).mockImplementation((path: string) => {
    const table: Record<string, unknown> = {
      "/api/v1/strategies/mac-01/status": overrides.status ?? status,
      "/api/v1/strategies/mac-01/signals": signals,
      "/api/v1/strategies/mac-01/orders": orders,
      "/api/v1/strategies/mac-01/performance": performance,
      "/api/v1/strategies/mac-01/chart": overrides.chart ?? chart,
    };
    return Promise.resolve(table[path] as never);
  });
}

async function renderPage() {
  render(
    <MemoryRouter initialEntries={["/strategy"]}>
      <AppRoutes />
    </MemoryRouter>,
  );
  await act(async () => {
    await Promise.resolve();
  });
}

describe("StrategyPage", () => {
  beforeEach(() => {
    vi.mocked(apiGet).mockReset();
    vi.mocked(apiPost).mockReset();
    createChart.mockClear();
    setData.mockClear();
    createSeriesMarkers.mockClear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows paper mode, health, chart, P&L, signals and orders with no buy or sell button", async () => {
    mockApi();
    await renderPage();

    expect(screen.getByRole("heading", { name: "Strategy · MAC-01" })).toBeInTheDocument();
    expect(screen.getByText(STRATEGY_NOTICE)).toBeInTheDocument();
    expect(screen.getByText(/Mode: Paper · paper money/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Strategy" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("img", { name: /AAPL daily adjusted closes with SMA 20 and SMA 50/ })).toBeInTheDocument();
    expect(createChart).toHaveBeenCalled();
    expect(setData).toHaveBeenCalledWith([
      { time: "2026-11-05", value: 100 },
      { time: "2026-11-06", value: 110 },
    ]);
    expect(createSeriesMarkers).toHaveBeenCalledWith(
      expect.anything(),
      [expect.objectContaining({ time: "2026-11-06", shape: "arrowUp" })],
    );
    expect(screen.getByText("$0")).toBeInTheDocument();
    expect(screen.getByText("Unavailable")).toBeInTheDocument();
    expect(screen.getByRole("table", { name: /signals/ })).toHaveTextContent("BUY");
    expect(screen.getByRole("table", { name: /orders/ })).toHaveTextContent("$100.00 notional");
    expect(screen.queryByRole("button", { name: /buy|sell|submit|order/i })).not.toBeInTheDocument();
  });

  it("warns clearly when the config is in live mode", async () => {
    mockApi({ status: { ...status, config_mode: "live", money: "real", config_live_enabled: true } });
    await renderPage();

    expect(screen.getByText(/Mode: LIVE · real money/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /buy|sell|submit/i })).not.toBeInTheDocument();
  });

  it("needs two clicks to engage the kill switch", async () => {
    mockApi();
    vi.mocked(apiPost).mockResolvedValue({ ...status, kill_switch: true } as never);
    await renderPage();

    fireEvent.click(screen.getByRole("button", { name: "Engage kill switch" }));
    expect(apiPost).not.toHaveBeenCalled();
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Confirm: block every MAC-01 order" }));
    });

    expect(apiPost).toHaveBeenCalledWith("/api/v1/strategies/mac-01/kill-switch", {});
  });

  it("cancel leaves the kill switch alone", async () => {
    mockApi();
    await renderPage();

    fireEvent.click(screen.getByRole("button", { name: "Engage kill switch" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(apiPost).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Engage kill switch" })).toBeInTheDocument();
  });

  it("pauses through the API", async () => {
    mockApi();
    vi.mocked(apiPost).mockResolvedValue({ ...status, paused: true } as never);
    await renderPage();

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Pause" }));
    });

    expect(apiPost).toHaveBeenCalledWith("/api/v1/strategies/mac-01/pause", {});
    expect(screen.getByRole("button", { name: "Resume" })).toBeDisabled();
  });

  it("does not invent a chart when none is stored", async () => {
    mockApi({
      chart: { ...chart, available: false, points: [], markers: [], note: "No runner pass has stored a chart yet." },
    });
    await renderPage();

    expect(screen.getByText("No runner pass has stored a chart yet.")).toBeInTheDocument();
    expect(createChart).not.toHaveBeenCalled();
  });

  it("reports an unreachable API", async () => {
    vi.mocked(apiGet).mockRejectedValue(new Error("offline"));
    await renderPage();

    expect(screen.getByRole("alert")).toHaveTextContent("The MAC-01 API is not reachable.");
  });
});
