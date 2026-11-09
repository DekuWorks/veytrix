import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiGet } from "../api/client";
import type { MarketHealthResponse, SystemStatusResponse } from "../api/types";
import { AppRoutes } from "../App";

vi.mock("../api/client", () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
}));

const posture: SystemStatusResponse = {
  status: "ok",
  service: "veytrix-api",
  env: "local",
  trading_mode: "paper",
  live_broker: "disabled",
  auth: "not_configured",
  database: "up",
  execution_permitted: false,
  order_submitted: false,
  order_route: "absent",
  agents_registered: 9,
  agents_can_trade: false,
  sample_data: true,
};

const health: MarketHealthResponse = {
  status: "degraded",
  source: "coinbase-exchange",
  stale_after_seconds: 120,
  sample_included: false,
  executable: false,
  execution_permitted: false,
  order_submitted: false,
  order_route: "absent",
  note: "Public Coinbase tickers. No order is sent.",
  feeds: [
    {
      symbol: "BTC-USD",
      status: "up",
      source_id: "coinbase-exchange",
      synthetic: false,
      retrieved_at: "2026-11-09T01:00:00Z",
      trade_time: "2026-11-09T00:59:00Z",
      age_seconds: 30,
      price: "75764.49",
      note: "Last Coinbase print is within 120 seconds.",
    },
    {
      symbol: "ETH-USD",
      status: "down",
      source_id: "coinbase-exchange",
      synthetic: false,
      retrieved_at: null,
      trade_time: null,
      age_seconds: null,
      price: null,
      note: "Coinbase ticker is unavailable. No substitute price was generated.",
    },
    {
      symbol: "SOL-USD",
      status: "stale",
      source_id: "coinbase-exchange",
      synthetic: false,
      retrieved_at: "2026-11-09T00:50:00Z",
      trade_time: "2026-11-09T00:50:00Z",
      age_seconds: 600,
      price: "180.25",
      note: "Last Coinbase print is older than 120 seconds.",
    },
  ],
};

function renderSystem() {
  render(
    <MemoryRouter initialEntries={["/system"]}>
      <AppRoutes />
    </MemoryRouter>,
  );
}

function mockGets(systemBody: unknown, marketBody: unknown) {
  vi.mocked(apiGet).mockImplementation((path: string) => {
    if (path === "/api/v1/system/status") {
      return Promise.resolve(systemBody);
    }
    if (path === "/api/v1/market/health") {
      return Promise.resolve(marketBody);
    }
    return Promise.reject(new Error(path));
  });
}

describe("system health page", () => {
  beforeEach(() => {
    vi.mocked(apiGet).mockReset();
  });

  it("shows local posture and a down feed without a price", async () => {
    mockGets(posture, health);
    renderSystem();

    expect(await screen.findByRole("heading", { name: "System health" })).toBeInTheDocument();
    expect(screen.getByText("absent")).toBeInTheDocument();
    expect(screen.getByText("disabled")).toBeInTheDocument();
    expect(screen.getByText("9")).toBeInTheDocument();
    expect(screen.getByText("75764.49")).toBeInTheDocument();
    expect(screen.getByText("180.25 stale")).toBeInTheDocument();
    expect(screen.getByText(/No substitute price was generated/)).toBeInTheDocument();
    expect(screen.queryByText("3200.10")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /approve|transfer|submit|enable|save|live/i }),
    ).not.toBeInTheDocument();
    expect(vi.mocked(apiGet)).toHaveBeenCalledWith("/api/v1/system/status");
    expect(vi.mocked(apiGet)).toHaveBeenCalledWith("/api/v1/market/health");
  });

  it("keeps the posture when market health fails", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path === "/api/v1/system/status") {
        return Promise.resolve(posture);
      }
      return Promise.reject(new Error("down"));
    });
    renderSystem();

    expect(await screen.findByText("absent")).toBeInTheDocument();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Market health is unavailable. No substitute price was generated.",
    );
    expect(screen.queryByText("75764.49")).not.toBeInTheDocument();
  });

  it("hides a feed list that claims an order was submitted", async () => {
    mockGets(posture, { ...health, order_submitted: true });
    renderSystem();

    expect(await screen.findByText("absent")).toBeInTheDocument();
    expect(
      await screen.findByText("Market health is unavailable. No substitute price was generated."),
    ).toBeInTheDocument();
    expect(screen.queryByText("75764.49")).not.toBeInTheDocument();
  });

  it("hides a posture that says a desk can trade", async () => {
    mockGets({ ...posture, agents_can_trade: true }, health);
    renderSystem();

    expect(await screen.findByText("75764.49")).toBeInTheDocument();
    expect(
      await screen.findByText("System status is unavailable. No broker balance was invented."),
    ).toBeInTheDocument();
    expect(screen.queryByText("absent")).not.toBeInTheDocument();
  });
});
