import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiDelete, apiGet } from "../api/client";
import type { PaperPositionResponse, TickerResponse } from "../api/types";
import { AppRoutes } from "../App";

vi.mock("../api/client", () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiDelete: vi.fn(),
}));

const eth: TickerResponse = {
  symbol: "ETH-USD",
  venue: "COINBASE",
  source_id: "coinbase-exchange",
  synthetic: false,
  price: "2234.00",
  bid: "2234.00",
  ask: "2234.01",
  size: "0.1",
  volume: "10",
  trade_time: "2026-11-08T04:41:00.000000Z",
  trade_id: 2,
  retrieved_at: "2026-11-08T04:41:00Z",
  disclaimer: "Live ETH-USD last trade. No order is sent.",
};

const stored: PaperPositionResponse = {
  id: "paper-1",
  symbol: "ETH-USD",
  entry: "2233.58",
  stop: "2200.00",
  shares: 4,
  notional: "8934.32",
  planned_risk: "134.32",
  binding_constraint: "allocation",
  exchange_time: "2026-11-08T04:21:04.000000Z",
  recorded_at: "2026-11-08T04:40:00.000Z",
  execution_permitted: false,
  order_submitted: false,
};

function renderPortfolio() {
  render(
    <MemoryRouter initialEntries={["/portfolio"]}>
      <AppRoutes />
    </MemoryRouter>,
  );
}

describe("portfolio page", () => {
  beforeEach(() => {
    vi.useRealTimers();
    vi.mocked(apiGet).mockReset();
    vi.mocked(apiDelete).mockReset();
  });

  it("shows an empty paper list and does not ask for a ticker", async () => {
    vi.mocked(apiGet).mockResolvedValue({ positions: [] });
    renderPortfolio();

    expect(await screen.findByText("No paper positions recorded yet.")).toBeInTheDocument();
    expect(screen.getByText(/not a brokerage position/)).toBeInTheDocument();
    expect(screen.getByText(/No order is sent/)).toBeInTheDocument();
    expect(vi.mocked(apiGet)).toHaveBeenCalledWith("/api/v1/portfolio/positions");
    expect(vi.mocked(apiGet)).not.toHaveBeenCalledWith(expect.stringContaining("/ticker"));
  });

  it("shows one stored paper row, a live mark, and removes it", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path === "/api/v1/portfolio/positions") {
        return Promise.resolve({ positions: [stored] });
      }
      return Promise.resolve(eth);
    });
    vi.mocked(apiDelete).mockResolvedValue(undefined);
    renderPortfolio();

    expect(await screen.findByRole("heading", { name: "ETH-USD" })).toBeInTheDocument();
    expect(screen.getByText("Paper")).toBeInTheDocument();
    expect(screen.getByText("2233.58")).toBeInTheDocument();
    expect(screen.getByText("2200.00")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
    expect(screen.getByText("8934.32")).toBeInTheDocument();
    expect(screen.getByText("134.32")).toBeInTheDocument();
    expect(screen.getByText("allocation")).toBeInTheDocument();
    expect(screen.getByText(/Exchange time of the print 2026-11-08T04:21:04\.000000Z/)).toBeInTheDocument();
    expect(await screen.findByText(/Last trade \$2,234\.00/)).toBeInTheDocument();
    expect(screen.getByText(/Unrealised \+\$1\.68 USD/)).toBeInTheDocument();
    expect(screen.getByText("Mark from the Coinbase print. Not a fill.")).toBeInTheDocument();
    expect(screen.getByText("Distance to stop +$34 (+1.55%).")).toBeInTheDocument();
    expect(vi.mocked(apiGet)).toHaveBeenCalledWith("/api/v1/market/instruments/ETH-USD/ticker");
    expect(vi.mocked(apiGet)).not.toHaveBeenCalledWith("/api/v1/risk/size");

    fireEvent.click(screen.getByRole("button", { name: "Remove" }));

    expect(await screen.findByText("No paper positions recorded yet.")).toBeInTheDocument();
    expect(vi.mocked(apiDelete)).toHaveBeenCalledWith("/api/v1/portfolio/positions/paper-1");
  });

  it("keeps the stored row and says the mark is unavailable when the ticker fails", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path === "/api/v1/portfolio/positions") {
        return Promise.resolve({ positions: [stored] });
      }
      return Promise.reject(new Error("down"));
    });
    renderPortfolio();

    expect(await screen.findByText("Mark unavailable")).toBeInTheDocument();
    expect(screen.getByText("2233.58")).toBeInTheDocument();
    expect(screen.queryByText(/Last trade/)).not.toBeInTheDocument();
    expect(screen.getByText("Mark from the Coinbase print. Not a fill.")).toBeInTheDocument();
    expect(screen.getByText("Distance to stop is unavailable.")).toBeInTheDocument();
    expect(screen.queryByText(/Print is stale/)).not.toBeInTheDocument();
    expect(screen.queryByText("Exchange time is unreadable.")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "ETH-USD" })).toBeInTheDocument();
  });

  it("says the store is unavailable and does not invent an empty list", async () => {
    vi.mocked(apiGet).mockRejectedValue(new Error("down"));
    renderPortfolio();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Paper positions are unavailable. No row was invented.",
    );
    expect(screen.queryByText("No paper positions recorded yet.")).not.toBeInTheDocument();
  });

  it("refreshes the mark from the next print", async () => {
    vi.useFakeTimers();
    let price = "2234.00";
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path === "/api/v1/portfolio/positions") {
        return Promise.resolve({ positions: [stored] });
      }
      return Promise.resolve({
        ...eth,
        price,
        trade_time: price === "2234.00" ? eth.trade_time : "2026-11-08T04:41:02.000000Z",
      });
    });
    renderPortfolio();
    await act(async () => {
      await Promise.resolve();
    });

    expect(screen.getByText(/Last trade \$2,234\.00/)).toBeInTheDocument();
    expect(screen.getByText(/Unrealised \+\$1\.68 USD/)).toBeInTheDocument();
    expect(screen.getByText("Distance to stop +$34 (+1.55%).")).toBeInTheDocument();
    price = "2235.00";
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
    });

    expect(screen.getByText(/Last trade \$2,235\.00/)).toBeInTheDocument();
    expect(screen.getByText(/Unrealised \+\$5\.68 USD/)).toBeInTheDocument();
    expect(screen.getByText("Distance to stop +$35 (+1.59%).")).toBeInTheDocument();
    expect(screen.queryByText("$2,234.00")).not.toBeInTheDocument();
  });
});

const MARK_NOW = Date.parse("2026-11-08T05:40:00.000Z");

describe("portfolio mark freshness", () => {
  beforeEach(() => {
    vi.useRealTimers();
    vi.mocked(apiGet).mockReset();
    vi.spyOn(Date, "now").mockReturnValue(MARK_NOW);
  });

  afterEach(() => {
    vi.mocked(Date.now).mockRestore();
  });

  it("keeps the mark and says the print is stale when the exchange time is 21 seconds old", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path === "/api/v1/portfolio/positions") {
        return Promise.resolve({ positions: [stored] });
      }
      return Promise.resolve({ ...eth, trade_time: "2026-11-08T05:39:39.000000000Z" });
    });
    renderPortfolio();

    expect(await screen.findByText(/Last trade \$2,234\.00/)).toBeInTheDocument();
    expect(screen.getByText(/Unrealised \+\$1\.68 USD/)).toBeInTheDocument();
    expect(screen.getByText("Distance to stop +$34 (+1.55%).")).toBeInTheDocument();
    expect(screen.getByText("Print is stale. Age 21 seconds.")).toBeInTheDocument();
    expect(screen.getByText("Mark from the Coinbase print. Not a fill.")).toBeInTheDocument();
  });

  it("does not mark a 5-second-old print stale", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path === "/api/v1/portfolio/positions") {
        return Promise.resolve({ positions: [stored] });
      }
      return Promise.resolve({ ...eth, trade_time: "2026-11-08T05:39:55.000Z" });
    });
    renderPortfolio();

    expect(await screen.findByText(/Last trade \$2,234\.00/)).toBeInTheDocument();
    expect(screen.getByText("Distance to stop +$34 (+1.55%).")).toBeInTheDocument();
    expect(screen.queryByText(/Print is stale/)).not.toBeInTheDocument();
    expect(screen.queryByText("Exchange time is unreadable.")).not.toBeInTheDocument();
  });

  it("does not treat an unreadable mark time as current", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path === "/api/v1/portfolio/positions") {
        return Promise.resolve({ positions: [stored] });
      }
      return Promise.resolve({ ...eth, trade_time: "2026-11-08Tnot-readableZ" });
    });
    renderPortfolio();

    expect(await screen.findByText(/Last trade \$2,234\.00/)).toBeInTheDocument();
    expect(screen.getByText(/Unrealised \+\$1\.68 USD/)).toBeInTheDocument();
    expect(screen.getByText("Distance to stop +$34 (+1.55%).")).toBeInTheDocument();
    expect(screen.getByText("Exchange time is unreadable.")).toBeInTheDocument();
    expect(screen.queryByText(/Print is stale/)).not.toBeInTheDocument();
  });
});

describe("portfolio unrealised percent", () => {
  beforeEach(() => {
    vi.useRealTimers();
    vi.mocked(apiGet).mockReset();
    vi.mocked(apiDelete).mockReset();
  });

  function renderRow(price: string | null, entry: string) {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path === "/api/v1/portfolio/positions") {
        return Promise.resolve({ positions: [{ ...stored, entry, stop: "90.00" }] });
      }
      if (price === null) {
        return Promise.reject(new Error("down"));
      }
      return Promise.resolve({ ...eth, price });
    });
    renderPortfolio();
  }

  it("shows a gain as a percent of the entry", async () => {
    renderRow("110.00", "100.00");

    expect(await screen.findByText("Unrealised percent +10.00%.")).toBeInTheDocument();
    expect(screen.getByText(/Unrealised \+\$40 USD/)).toBeInTheDocument();
    expect(screen.getByText("Distance to stop +$20 (+22.22%).")).toBeInTheDocument();
    expect(screen.queryByText("2233.58")).not.toBeInTheDocument();
    expect(screen.getByText("100.00")).toBeInTheDocument();
    expect(screen.getByText("Mark from the Coinbase print. Not a fill.")).toBeInTheDocument();
  });

  it("shows a loss as a percent of the entry", async () => {
    renderRow("90.00", "100.00");

    expect(await screen.findByText("Unrealised percent -10.00%.")).toBeInTheDocument();
    expect(screen.getByText(/Unrealised -\$40 USD/)).toBeInTheDocument();
    expect(screen.getByText(/Last trade \$90\.00/)).toBeInTheDocument();
  });

  it("shows a flat print as 0.00 percent", async () => {
    renderRow("100.00", "100.00");

    expect(await screen.findByText("Unrealised percent 0.00%.")).toBeInTheDocument();
    expect(screen.getByText(/Last trade \$100\.00/)).toBeInTheDocument();
    expect(screen.getByText(/Unrealised \$0 USD/)).toBeInTheDocument();
  });

  it("keeps the row when the last trade is missing", async () => {
    renderRow(null, "100.00");

    expect(await screen.findByText("Unrealised percent is unavailable.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "ETH-USD" })).toBeInTheDocument();
    expect(screen.getByText("100.00")).toBeInTheDocument();
    expect(screen.getByText("Mark unavailable")).toBeInTheDocument();
    expect(screen.getByText("Distance to stop is unavailable.")).toBeInTheDocument();
    expect(screen.queryByText(/Last trade/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Unrealised percent [+-]/)).not.toBeInTheDocument();
    expect(screen.queryByText("Unrealised percent 0.00%.")).not.toBeInTheDocument();
  });
});
