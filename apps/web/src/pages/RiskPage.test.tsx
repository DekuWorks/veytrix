import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiGet, apiPost } from "../api/client";
import type { SizeResponse, TickerResponse } from "../api/types";
import { AppRoutes } from "../App";

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

const btc: TickerResponse = {
  symbol: "BTC-USD",
  venue: "COINBASE",
  source_id: "coinbase-exchange",
  synthetic: false,
  price: "75815.71",
  bid: "75815.71",
  ask: "75815.72",
  size: "0.01",
  volume: "10",
  trade_time: "2026-11-08T04:21:15.000000Z",
  trade_id: 1,
  retrieved_at: "2026-11-08T04:21:15Z",
  disclaimer: "Live BTC-USD last trade. No order is sent.",
};

const eth: TickerResponse = {
  ...btc,
  symbol: "ETH-USD",
  price: "2233.58",
  bid: "2233.58",
  ask: "2233.59",
  trade_time: "2026-11-08T04:21:04.000000Z",
  trade_id: 2,
  disclaimer: "Live ETH-USD last trade. No order is sent.",
};

const sized: SizeResponse = {
  symbol: "ETH-USD",
  shares: 4,
  binding_constraint: "allocation",
  stop_distance: "33.58",
  planned_risk_amount: "134.32",
  risk_budget: "500.00",
  notional: "8934.32",
  account_equity: "100000.00",
  entry_price: "2233.58",
  stop_price: "2200.00",
  risk_fraction: "0.005",
  max_allocation_fraction: "0.10",
  daily_loss_stop_fraction: "0.01",
  weekly_loss_stop_fraction: "0.03",
  policy_name: "experimental-paper-default",
  warning: null,
  note: "Stored with the size. No order is sent.",
  execution_permitted: false,
  order_submitted: false,
  daily_stop_enforced: false,
  weekly_stop_enforced: false,
};

function renderRisk() {
  render(
    <MemoryRouter initialEntries={["/risk"]}>
      <AppRoutes />
    </MemoryRouter>,
  );
}

describe("risk page", () => {
  beforeEach(() => {
    vi.useRealTimers();
    vi.mocked(apiGet).mockReset();
    vi.mocked(apiPost).mockReset();
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.includes("/ETH-USD/ticker")) {
        return Promise.resolve(eth);
      }
      if (path.includes("/BTC-USD/ticker")) {
        return Promise.resolve(btc);
      }
      return Promise.reject(new Error(`unexpected ${path}`));
    });
  });

  it("calculates a paper size and does not send an order", async () => {
    renderRisk();

    expect(await screen.findByDisplayValue("75815.71")).toBeInTheDocument();
    expect(screen.getByText(/Exchange time 2026-11-08T04:21:15\.000000Z/)).toBeInTheDocument();
    expect(screen.getAllByText(/No order is sent/).length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: /send|trade|order/i })).not.toBeInTheDocument();
    expect(vi.mocked(apiPost)).not.toHaveBeenCalled();
  });

  it("switches the entry to the ETH-USD print", async () => {
    renderRisk();

    expect(await screen.findByDisplayValue("75815.71")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "ETH-USD" }));

    expect(await screen.findByDisplayValue("2233.58")).toBeInTheDocument();
    expect(screen.queryByDisplayValue("75815.71")).not.toBeInTheDocument();
    expect(screen.getByText(/Exchange time 2026-11-08T04:21:04\.000000Z/)).toBeInTheDocument();
  });

  it("stops overwriting an edited entry and reset copies the live print", async () => {
    vi.useFakeTimers();
    let price = "75815.71";
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.includes("/BTC-USD/ticker")) {
        return Promise.resolve({ ...btc, price });
      }
      return Promise.reject(new Error(path));
    });
    renderRisk();
    await act(async () => {
      await Promise.resolve();
    });

    const entry = screen.getByRole("textbox", { name: "Entry price" });
    expect(entry).toHaveValue("75815.71");
    fireEvent.change(entry, { target: { value: "50.00" } });
    price = "76000.00";
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
    });

    expect(entry).toHaveValue("50.00");
    expect(screen.getByText(/Live BTC-USD print 76000.00/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Reset to live print" }));
    expect(entry).toHaveValue("76000.00");
    expect(screen.getByText(/Exchange time 2026-11-08T04:21:15\.000000Z/)).toBeInTheDocument();
  });

  it("does not invent an entry when the print is down", async () => {
    vi.mocked(apiGet).mockRejectedValue(new Error("down"));
    renderRisk();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Live BTC-USD print is unavailable. No entry price was invented.",
    );
    expect(screen.getByRole("textbox", { name: "Entry price" })).toHaveValue("");
    expect(screen.queryByDisplayValue("75815.71")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reset to live print" })).toBeDisabled();
  });

  it("shows the spread beside the live entry and does not replace the entry", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.includes("/BTC-USD/ticker")) {
        return Promise.resolve({ ...btc, bid: "100.00", ask: "100.10" });
      }
      return Promise.reject(new Error(path));
    });
    renderRisk();

    expect(await screen.findByDisplayValue("75815.71")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Entry price" })).toHaveValue("75815.71");
    expect(screen.getByText("Spread $0.10 (10.00 bp).")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /send|trade|order/i })).not.toBeInTheDocument();
  });

  it("calculates a paper size and keeps execution closed", async () => {
    vi.mocked(apiPost).mockResolvedValue(sized);
    renderRisk();
    fireEvent.click(screen.getByRole("button", { name: "ETH-USD" }));
    expect(await screen.findByDisplayValue("2233.58")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("textbox", { name: "Account equity" }), {
      target: { value: "100000.00" },
    });
    fireEvent.change(screen.getByRole("textbox", { name: "Stop price" }), {
      target: { value: "2200.00" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Calculate paper size" }));

    expect(await screen.findByText("4")).toBeInTheDocument();
    expect(screen.getByText("allocation")).toBeInTheDocument();
    expect(screen.getByText("134.32")).toBeInTheDocument();
    expect(screen.getByText("8934.32")).toBeInTheDocument();
    expect(screen.getAllByText("false").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("No order is sent.").length).toBeGreaterThan(0);
    expect(vi.mocked(apiPost)).toHaveBeenCalledWith("/api/v1/risk/size", {
      symbol: "ETH-USD",
      account_equity: "100000.00",
      entry_price: "2233.58",
      stop_price: "2200.00",
      side: "long",
    });
  });

  it("records the paper size through the portfolio route", async () => {
    vi.mocked(apiPost).mockImplementation((path: string) => {
      if (path === "/api/v1/portfolio/positions") {
        return Promise.resolve({
          id: "paper-1",
          symbol: "ETH-USD",
          entry: "2233.58",
          stop: "2200.00",
          shares: 4,
          notional: "8934.32",
          planned_risk: "134.32",
          binding_constraint: "allocation",
          exchange_time: "2026-11-08T04:21:04.000000Z",
          recorded_at: "2026-11-08T04:40:00Z",
          execution_permitted: false,
          order_submitted: false,
        });
      }
      return Promise.resolve(sized);
    });
    renderRisk();
    fireEvent.click(screen.getByRole("button", { name: "ETH-USD" }));
    expect(await screen.findByDisplayValue("2233.58")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("textbox", { name: "Account equity" }), {
      target: { value: "100000.00" },
    });
    fireEvent.change(screen.getByRole("textbox", { name: "Stop price" }), {
      target: { value: "2200.00" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Calculate paper size" }));

    expect(await screen.findByRole("button", { name: "Record paper position" })).toBeInTheDocument();
    expect(screen.getByText(/It is not a fill/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Record paper position" }));

    expect(await screen.findByText("Recorded on this machine. No order is sent.")).toBeInTheDocument();
    expect(vi.mocked(apiPost)).toHaveBeenNthCalledWith(2, "/api/v1/portfolio/positions", {
      symbol: "ETH-USD",
      entry: "2233.58",
      stop: "2200.00",
      shares: 4,
      notional: "8934.32",
      planned_risk: "134.32",
      binding_constraint: "allocation",
      exchange_time: "2026-11-08T04:21:04.000000Z",
    });
    expect(screen.queryByRole("button", { name: /send|place order|submit order/i })).not.toBeInTheDocument();
  });

  it("does not pretend a paper size was saved when the store is down", async () => {
    vi.mocked(apiPost).mockImplementation((path: string) => {
      if (path === "/api/v1/portfolio/positions") {
        return Promise.reject(new Error("down"));
      }
      return Promise.resolve(sized);
    });
    renderRisk();
    fireEvent.click(screen.getByRole("button", { name: "ETH-USD" }));
    expect(await screen.findByDisplayValue("2233.58")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("textbox", { name: "Account equity" }), {
      target: { value: "100000.00" },
    });
    fireEvent.change(screen.getByRole("textbox", { name: "Stop price" }), {
      target: { value: "2200.00" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Calculate paper size" }));
    fireEvent.click(await screen.findByRole("button", { name: "Record paper position" }));

    expect(
      await screen.findByText("The paper position store is unavailable. This paper size was not recorded."),
    ).toBeInTheDocument();
    expect(screen.queryByText("Recorded on this machine. No order is sent.")).not.toBeInTheDocument();
  });

  it("does not record a paper size when the print has no exchange time", async () => {
    vi.mocked(apiGet).mockRejectedValue(new Error("down"));
    vi.mocked(apiPost).mockResolvedValue(sized);
    renderRisk();

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("textbox", { name: "Account equity" }), {
      target: { value: "100000.00" },
    });
    fireEvent.change(screen.getByRole("textbox", { name: "Entry price" }), {
      target: { value: "2233.58" },
    });
    fireEvent.change(screen.getByRole("textbox", { name: "Stop price" }), {
      target: { value: "2200.00" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Calculate paper size" }));
    fireEvent.click(await screen.findByRole("button", { name: "Record paper position" }));

    expect(screen.getByText("The Coinbase print is unavailable. This paper size was not recorded.")).toBeInTheDocument();
    expect(vi.mocked(apiPost).mock.calls.some(([path]) => path === "/api/v1/portfolio/positions")).toBe(
      false,
    );
  });
});

const ENTRY_NOW = Date.parse("2026-11-08T05:40:00.000Z");

describe("risk entry freshness", () => {
  beforeEach(() => {
    vi.mocked(apiGet).mockReset();
    vi.mocked(apiPost).mockReset();
    vi.spyOn(Date, "now").mockReturnValue(ENTRY_NOW);
  });

  afterEach(() => {
    vi.mocked(Date.now).mockRestore();
  });

  it("shows the stale line beside a 21-second-old entry and keeps the price", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.includes("/BTC-USD/ticker")) {
        return Promise.resolve({ ...btc, trade_time: "2026-11-08T05:39:39.000000000Z" });
      }
      return Promise.reject(new Error(path));
    });
    renderRisk();

    expect(await screen.findByDisplayValue("75815.71")).toBeInTheDocument();
    expect(screen.getByText("Print is stale. Age 21 seconds.")).toBeInTheDocument();
    expect(screen.getByText(/Exchange time 2026-11-08T05:39:39\.000000000Z/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /send|trade|order/i })).not.toBeInTheDocument();
  });

  it("does not mark a 5-second-old entry stale", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.includes("/BTC-USD/ticker")) {
        return Promise.resolve({ ...btc, trade_time: "2026-11-08T05:39:55.000Z" });
      }
      return Promise.reject(new Error(path));
    });
    renderRisk();

    expect(await screen.findByDisplayValue("75815.71")).toBeInTheDocument();
    expect(screen.getByText(/Exchange time 2026-11-08T05:39:55\.000Z/)).toBeInTheDocument();
    expect(screen.queryByText(/Print is stale/)).not.toBeInTheDocument();
    expect(screen.queryByText("Exchange time is unreadable.")).not.toBeInTheDocument();
  });

  it("does not treat an unreadable exchange time as a current entry", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.includes("/BTC-USD/ticker")) {
        return Promise.resolve({ ...btc, trade_time: "2026-11-08Tnot-readableZ" });
      }
      return Promise.reject(new Error(path));
    });
    renderRisk();

    expect(await screen.findByDisplayValue("75815.71")).toBeInTheDocument();
    expect(screen.getByText("Exchange time is unreadable.")).toBeInTheDocument();
    expect(screen.queryByText(/Print is stale/)).not.toBeInTheDocument();
  });
});

describe("risk stop distance", () => {
  beforeEach(() => {
    vi.useRealTimers();
    vi.mocked(apiGet).mockReset();
    vi.mocked(apiPost).mockReset();
    vi.mocked(apiGet).mockResolvedValue(btc);
  });

  async function fill(entry: string, stop: string) {
    renderRisk();
    expect(await screen.findByDisplayValue("75815.71")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("textbox", { name: "Entry price" }), { target: { value: entry } });
    fireEvent.change(screen.getByRole("textbox", { name: "Stop price" }), { target: { value: stop } });
  }

  it("shows 4.00 percent before calculate is pressed", async () => {
    await fill("50", "48");

    expect(screen.getByText("Stop distance $2.00 (4.00%).")).toBeInTheDocument();
    expect(screen.getAllByText("Stop distance $2.00 (4.00%).")).toHaveLength(1);
    expect(screen.queryByText("Execution permitted")).not.toBeInTheDocument();
    expect(vi.mocked(apiPost)).not.toHaveBeenCalled();
  });

  it("says the distance is unavailable when the stop equals the entry", async () => {
    await fill("50", "50");

    expect(screen.getAllByText("Stop distance is unavailable.")).toHaveLength(1);
    expect(screen.queryByText(/Stop distance \$/)).not.toBeInTheDocument();
    expect(vi.mocked(apiPost)).not.toHaveBeenCalled();
  });

  it("says the distance is unavailable when the stop is above the entry", async () => {
    await fill("50", "51");

    expect(screen.getAllByText("Stop distance is unavailable.")).toHaveLength(1);
    expect(screen.queryByText("Stop distance -$1.00 (-2.00%).")).not.toBeInTheDocument();
    expect(vi.mocked(apiPost)).not.toHaveBeenCalled();
  });

  it("says the distance is unavailable when the stop is missing", async () => {
    renderRisk();

    expect(await screen.findByDisplayValue("75815.71")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Stop price" })).toHaveValue("");
    expect(screen.getAllByText("Stop distance is unavailable.")).toHaveLength(1);
    expect(screen.queryByText(/Stop distance \$/)).not.toBeInTheDocument();
    expect(vi.mocked(apiPost)).not.toHaveBeenCalled();
  });
});

describe("risk planned risk percent", () => {
  beforeEach(() => {
    vi.useRealTimers();
    vi.mocked(apiGet).mockReset();
    vi.mocked(apiPost).mockReset();
    vi.mocked(apiGet).mockResolvedValue(btc);
  });

  async function showResult(result: SizeResponse) {
    vi.mocked(apiPost).mockResolvedValue(result);
    renderRisk();
    expect(await screen.findByDisplayValue("75815.71")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("textbox", { name: "Account equity" }), {
      target: { value: result.account_equity },
    });
    fireEvent.change(screen.getByRole("textbox", { name: "Stop price" }), {
      target: { value: "90.00" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Calculate paper size" }));
    expect(await screen.findByText("Execution permitted")).toBeInTheDocument();
  }

  it("shows planned risk as a percent of the entered equity", async () => {
    await showResult({ ...sized, shares: 7, planned_risk_amount: "400", account_equity: "100000", notional: "1000" });

    expect(screen.getByText("Planned risk percent 0.40%.")).toBeInTheDocument();
    expect(screen.getByText("400")).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument();
    expect(screen.getByText("1000")).toBeInTheDocument();
    expect(screen.getAllByText("false").length).toBeGreaterThanOrEqual(2);
    expect(vi.mocked(apiPost)).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("button", { name: /send|place order|submit order/i })).not.toBeInTheDocument();
  });

  it("shows 0.00 percent when planned risk is zero and equity is positive", async () => {
    await showResult({ ...sized, shares: 3, planned_risk_amount: "0.00", account_equity: "100000.00", notional: "1.00" });

    expect(screen.getByText("Planned risk percent 0.00%.")).toBeInTheDocument();
    expect(screen.getByText("0.00")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getAllByText("false").length).toBeGreaterThanOrEqual(2);
  });

  it("keeps the result when equity is zero", async () => {
    await showResult({ ...sized, shares: 4, planned_risk_amount: "400", account_equity: "0", notional: "10.00" });

    expect(screen.getByText("Planned risk percent is unavailable.")).toBeInTheDocument();
    expect(screen.getByText("400")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
    expect(screen.getByText("10.00")).toBeInTheDocument();
    expect(screen.getAllByText("false").length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText("Planned risk percent 0.00%.")).not.toBeInTheDocument();
    expect(screen.queryByText(/Planned risk percent \d/)).not.toBeInTheDocument();
  });
});
