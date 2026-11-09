import { act, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiGet, apiPost } from "../api/client";
import type { BarResponse, BarsResponse } from "../api/types";
import { AppRoutes } from "../App";

vi.mock("../api/client", () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
}));

function bar(start: string, close: string): BarResponse {
  return { bar_start: start, open: close, high: close, low: close, close, volume: "1" };
}

function stamp(index: number): string {
  return `2026-11-08T04:${String(index).padStart(2, "0")}:00Z`;
}

function series(
  symbol: "BTC-USD" | "ETH-USD" | "SOL-USD",
  closes: readonly string[],
  retrievedAt: string,
): BarsResponse {
  return {
    symbol,
    venue: "COINBASE",
    asset_type: "crypto",
    currency: "USD",
    source_id: "coinbase-exchange",
    interval: "1m",
    seed: null,
    synthetic: false,
    calendar_note: "Coinbase personal display.",
    disclaimer: "Personal display. No order is sent.",
    last_close: closes.at(-1) ?? null,
    previous_close: null,
    change: null,
    change_percent: null,
    retrieved_at: retrievedAt,
    source_url: null,
    bars: closes.map((close, index) => bar(stamp(index), close)),
  };
}

const btc = series("BTC-USD", ["100", "110", "90", "95", "80", "88", "89"], "2026-11-08T04:45:00Z");
const eth = series("ETH-USD", ["2100", "2111"], "2026-11-08T04:45:01Z");
const sol = series("SOL-USD", ["180.00", "186.40"], "2026-11-08T04:45:02Z");

function renderEvents() {
  render(
    <MemoryRouter initialEntries={["/events"]}>
      <AppRoutes />
    </MemoryRouter>,
  );
}

describe("events page", () => {
  beforeEach(() => {
    vi.useRealTimers();
    vi.mocked(apiGet).mockReset();
    vi.mocked(apiPost).mockReset();
  });

  it("ranks the largest absolute move first", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.includes("/SOL-USD/")) {
        return Promise.resolve(sol);
      }
      if (path.includes("/ETH-USD/")) {
        return Promise.resolve(eth);
      }
      return Promise.resolve(btc);
    });
    renderEvents();

    const btcRegion = await screen.findByRole("region", { name: "BTC-USD" });
    const rows = await within(btcRegion).findAllByRole("listitem");
    expect(rows).toHaveLength(5);
    expect(rows[0]).toHaveTextContent("-$20.00");
    expect(rows[0]).toHaveTextContent("Bar start 2026-11-08T04:02:00Z");
    expect(rows[0]).toHaveTextContent("-18.18%");
    expect(rows[1]).toHaveTextContent("-$15.00");
    expect(rows[4]).toHaveTextContent("+$5.00");
    expect(within(btcRegion).queryByText("+$1.00")).not.toBeInTheDocument();
    expect(screen.getByText("As of 2026-11-08T04:45:00Z")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Detected from Coinbase 1-minute candles on this machine. Not news. Not a trading signal. Not a consolidated quote. No order is sent.",
      ),
    ).toBeInTheDocument();
    expect(vi.mocked(apiGet)).toHaveBeenCalledWith("/api/v1/market/instruments/BTC-USD/bars?interval=1m&limit=180");
    expect(vi.mocked(apiGet)).toHaveBeenCalledWith("/api/v1/market/instruments/ETH-USD/bars?interval=1m&limit=180");
    expect(vi.mocked(apiGet)).toHaveBeenCalledWith("/api/v1/market/instruments/SOL-USD/bars?interval=1m&limit=180");
    expect(within(screen.getByRole("region", { name: "SOL-USD" })).getByText("$186.40")).toBeInTheDocument();
    expect(vi.mocked(apiPost)).not.toHaveBeenCalled();
  });

  it("shows a failed product as unavailable and keeps the other product", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.includes("/SOL-USD/")) {
        return Promise.resolve(sol);
      }
      if (path.includes("/ETH-USD/")) {
        return Promise.reject(new Error("down"));
      }
      return Promise.resolve(series("BTC-USD", ["100", "110", "90"], "2026-11-08T04:45:00Z"));
    });
    renderEvents();

    const ethRegion = await screen.findByRole("region", { name: "ETH-USD" });
    expect(await within(ethRegion).findByRole("alert")).toHaveTextContent(
      "ETH-USD is unavailable. No price was invented.",
    );
    expect(within(ethRegion).queryByText("$4,321.50")).not.toBeInTheDocument();
    expect(screen.queryByText("$4,321.50")).not.toBeInTheDocument();
    const btcRegion = screen.getByRole("region", { name: "BTC-USD" });
    expect(await within(btcRegion).findByText("-$20.00")).toBeInTheDocument();
  });

  it("drops a product's rows when a later refresh fails", async () => {
    vi.useFakeTimers();
    let ethDown = false;
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.includes("/SOL-USD/")) {
        return Promise.resolve(sol);
      }
      if (path.includes("/ETH-USD/") && ethDown) {
        return Promise.reject(new Error("down"));
      }
      if (path.includes("/ETH-USD/")) {
        return Promise.resolve(series("ETH-USD", ["4321.50", "4300.00"], "2026-11-08T04:46:00Z"));
      }
      return Promise.resolve(btc);
    });
    renderEvents();
    await act(async () => {
      await Promise.resolve();
    });

    expect(screen.getByText("-$21.50")).toBeInTheDocument();
    ethDown = true;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(45_000);
    });

    const ethRegion = screen.getByRole("region", { name: "ETH-USD" });
    expect(within(ethRegion).getByRole("alert")).toHaveTextContent(
      "ETH-USD is unavailable. No price was invented.",
    );
    expect(screen.queryByText("-$21.50")).not.toBeInTheDocument();
    expect(screen.queryByText("$4,321.50")).not.toBeInTheDocument();
    expect(screen.getByText("-$20.00")).toBeInTheDocument();
  });

  it("says when a product does not have enough bars", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) =>
      Promise.resolve(
        path.includes("/SOL-USD/")
          ? sol
          : path.includes("/ETH-USD/")
            ? series("ETH-USD", ["2111"], "2026-11-08T04:45:01Z")
            : series("BTC-USD", ["100", "bad", "130"], "2026-11-08T04:45:00Z"),
      ),
    );
    renderEvents();

    expect(await screen.findByText("There are not enough bars for ETH-USD.")).toBeInTheDocument();
    const btcRegion = screen.getByRole("region", { name: "BTC-USD" });
    expect(await within(btcRegion).findByText("+$30.00")).toBeInTheDocument();
    expect(within(btcRegion).queryByText("bad")).not.toBeInTheDocument();
  });
});

const CANDLE_NOW = Date.parse("2026-11-08T05:00:00.000Z");

function agedSeries(
  symbol: "BTC-USD" | "ETH-USD" | "SOL-USD",
  bars: readonly BarResponse[],
): BarsResponse {
  return {
    ...series(symbol, bars.map((item) => item.close), "2026-11-08T05:00:00Z"),
    bars: [...bars],
  };
}

describe("events candle age", () => {
  beforeEach(() => {
    vi.useRealTimers();
    vi.mocked(apiGet).mockReset();
    vi.mocked(apiPost).mockReset();
    vi.spyOn(Date, "now").mockReturnValue(CANDLE_NOW);
  });

  afterEach(() => {
    vi.mocked(Date.now).mockRestore();
    vi.useRealTimers();
  });

  function mockProducts(btcBars: readonly BarResponse[], ethBars: readonly BarResponse[] = btcBars) {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.includes("/ETH-USD/")) {
        return Promise.resolve(agedSeries("ETH-USD", ethBars));
      }
      if (path.includes("/SOL-USD/")) {
        return Promise.resolve(agedSeries("SOL-USD", ethBars));
      }
      return Promise.resolve(agedSeries("BTC-USD", btcBars));
    });
  }

  it("calls an open bucket current and does not call it stale", async () => {
    mockProducts([
      bar("2026-11-08T04:58:30Z", "100"),
      bar("2026-11-08T04:59:30Z", "110"),
    ]);
    renderEvents();

    const region = await screen.findByRole("region", { name: "BTC-USD" });
    expect(await within(region).findByText("Current 1-minute candle. 30 seconds left.")).toBeInTheDocument();
    expect(within(region).getByText("Bar start (UTC) 2026-11-08T04:59:30Z.")).toBeInTheDocument();
    expect(within(region).getByText("+$10.00")).toBeInTheDocument();
    expect(within(region).queryByText(/candle is stale/)).not.toBeInTheDocument();
    expect(
      within(region).getByText(
        "Candle time is the Coinbase bucket start. The close is not the live print. No order is sent.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Detected from Coinbase 1-minute candles on this machine. Not news. Not a trading signal. Not a consolidated quote. No order is sent.",
      ),
    ).toBeInTheDocument();
  });

  it("keeps the moves when the latest candle closed 91 seconds ago", async () => {
    mockProducts([
      bar("2026-11-08T04:56:29Z", "100"),
      bar("2026-11-08T04:57:29Z", "80"),
    ]);
    renderEvents();

    const region = await screen.findByRole("region", { name: "BTC-USD" });
    expect(await within(region).findByText("1-minute candle is stale. Age 91 seconds.")).toBeInTheDocument();
    expect(within(region).getByText("-$20.00")).toBeInTheDocument();
    expect(within(region).queryByText(/Current 1-minute candle/)).not.toBeInTheDocument();
  });

  it("does not call an unreadable bucket current", async () => {
    mockProducts([
      bar("2026-11-08T04:58:00Z", "100"),
      bar("2026-11-08T04:59:00Z", "110"),
      bar("not-a-time", "120"),
    ]);
    renderEvents();

    const region = await screen.findByRole("region", { name: "BTC-USD" });
    expect(await within(region).findByText("Candle time is unreadable.")).toBeInTheDocument();
    expect(within(region).getAllByText("+$10.00").length).toBeGreaterThan(0);
    expect(within(region).queryByText(/Current 1-minute candle/)).not.toBeInTheDocument();
  });

  it("drops a failed product's rows and does not keep its age line", async () => {
    vi.useFakeTimers();
    vi.spyOn(Date, "now").mockReturnValue(CANDLE_NOW);
    let ethDown = false;
    const open = [bar("2026-11-08T04:58:30Z", "100"), bar("2026-11-08T04:59:30Z", "110")];
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.includes("/ETH-USD/") && ethDown) {
        return Promise.reject(new Error("down"));
      }
      if (path.includes("/ETH-USD/")) {
        return Promise.resolve(agedSeries("ETH-USD", open));
      }
      if (path.includes("/SOL-USD/")) {
        return Promise.resolve(agedSeries("SOL-USD", open));
      }
      return Promise.resolve(agedSeries("BTC-USD", open));
    });
    renderEvents();
    await act(async () => {
      await Promise.resolve();
    });

    const ethRegion = screen.getByRole("region", { name: "ETH-USD" });
    expect(within(ethRegion).getByText("+$10.00")).toBeInTheDocument();
    expect(within(ethRegion).getByText("Current 1-minute candle. 30 seconds left.")).toBeInTheDocument();
    ethDown = true;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(45_000);
    });

    expect(within(ethRegion).getByRole("alert")).toHaveTextContent("ETH-USD is unavailable. No price was invented.");
    expect(within(ethRegion).queryByText("+$10.00")).not.toBeInTheDocument();
    expect(within(ethRegion).queryByText(/Current 1-minute candle/)).not.toBeInTheDocument();
    expect(within(ethRegion).queryByText(/candle is stale/)).not.toBeInTheDocument();
    const btcRegion = screen.getByRole("region", { name: "BTC-USD" });
    expect(within(btcRegion).getByText("+$10.00")).toBeInTheDocument();
    expect(within(btcRegion).getByText("Current 1-minute candle. 30 seconds left.")).toBeInTheDocument();
  });
});

describe("events move age", () => {
  beforeEach(() => {
    vi.useRealTimers();
    vi.mocked(apiGet).mockReset();
    vi.mocked(apiPost).mockReset();
    vi.spyOn(Date, "now").mockReturnValue(CANDLE_NOW);
  });

  afterEach(() => {
    vi.mocked(Date.now).mockRestore();
    vi.useRealTimers();
  });

  function mockProducts(btcBars: readonly BarResponse[]) {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.includes("/ETH-USD/")) {
        return Promise.resolve(agedSeries("ETH-USD", btcBars));
      }
      if (path.includes("/SOL-USD/")) {
        return Promise.resolve(agedSeries("SOL-USD", btcBars));
      }
      return Promise.resolve(agedSeries("BTC-USD", btcBars));
    });
  }

  it("shows 2 minutes for a move 125 seconds ago", async () => {
    mockProducts([
      bar("2026-11-08T04:56:55.000Z", "100"),
      bar("2026-11-08T04:57:55.000Z", "110"),
    ]);
    renderEvents();

    const region = await screen.findByRole("region", { name: "BTC-USD" });
    const row = await within(region).findByRole("listitem");
    expect(row).toHaveTextContent("+$10.00");
    expect(row).toHaveTextContent("Bar start 2026-11-08T04:57:55.000Z");
    expect(within(row).getByText("Move age 2 minutes.")).toBeInTheDocument();
    expect(
      within(row).getByText("Age of this 1-minute move. Not news. Not a trading signal. No order is sent."),
    ).toBeInTheDocument();
    expect(within(region).getByText("Last 1-minute candle closed 65 seconds ago.")).toBeInTheDocument();
    expect(vi.mocked(apiPost)).not.toHaveBeenCalled();
  });

  it("shows 0 minutes for a move 30 seconds ago", async () => {
    mockProducts([
      bar("2026-11-08T04:58:30.000Z", "100"),
      bar("2026-11-08T04:59:30.000Z", "90"),
    ]);
    renderEvents();

    const region = await screen.findByRole("region", { name: "BTC-USD" });
    const row = await within(region).findByRole("listitem");
    expect(row).toHaveTextContent("-$10.00");
    expect(within(row).getByText("Move age 0 minutes.")).toBeInTheDocument();
  });

  it("keeps the move when its candle time cannot be parsed", async () => {
    mockProducts([
      bar("2026-11-08T04:58:00Z", "100"),
      bar("not-a-time", "130"),
    ]);
    renderEvents();

    const region = await screen.findByRole("region", { name: "BTC-USD" });
    const row = await within(region).findByRole("listitem");
    expect(row).toHaveTextContent("+$30.00");
    expect(row).toHaveTextContent("Bar start not-a-time");
    expect(within(row).getByText("Move age is unavailable.")).toBeInTheDocument();
    expect(within(row).queryByText(/Move age \d/)).not.toBeInTheDocument();
    expect(within(region).getByText("$130.00")).toBeInTheDocument();
  });

  it("drops a product's rows when a later fetch fails", async () => {
    vi.useFakeTimers();
    vi.spyOn(Date, "now").mockReturnValue(CANDLE_NOW);
    let ethDown = false;
    const bars = [bar("2026-11-08T04:56:55.000Z", "100"), bar("2026-11-08T04:57:55.000Z", "80")];
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.includes("/ETH-USD/") && ethDown) {
        return Promise.reject(new Error("down"));
      }
      if (path.includes("/ETH-USD/")) {
        return Promise.resolve(agedSeries("ETH-USD", bars));
      }
      if (path.includes("/SOL-USD/")) {
        return Promise.resolve(agedSeries("SOL-USD", bars));
      }
      return Promise.resolve(agedSeries("BTC-USD", bars));
    });
    renderEvents();
    await act(async () => {
      await Promise.resolve();
    });

    const ethRegion = screen.getByRole("region", { name: "ETH-USD" });
    expect(within(ethRegion).getByText("-$20.00")).toBeInTheDocument();
    expect(within(ethRegion).getByText("Move age 2 minutes.")).toBeInTheDocument();
    ethDown = true;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(45_000);
    });

    expect(within(ethRegion).getByRole("alert")).toHaveTextContent("ETH-USD is unavailable. No price was invented.");
    expect(within(ethRegion).queryByText("-$20.00")).not.toBeInTheDocument();
    expect(within(ethRegion).queryByText(/Move age/)).not.toBeInTheDocument();
    const btcRegion = screen.getByRole("region", { name: "BTC-USD" });
    expect(within(btcRegion).getByText("-$20.00")).toBeInTheDocument();
    expect(within(btcRegion).getByText("Move age 2 minutes.")).toBeInTheDocument();
  });
});
