import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiGet, apiPost } from "../api/client";
import type { BarResponse, BarsResponse, TickerResponse } from "../api/types";
import { AppRoutes } from "../App";
import { averageOfLastCloses } from "../quant/average";

vi.mock("../api/client", () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
}));

function bar(start: string, close: string, high: string, low: string): BarResponse {
  return { bar_start: start, open: close, high, low, close, volume: "1" };
}

function stamp(index: number): string {
  return `2026-11-08T04:${String(index).padStart(2, "0")}:00Z`;
}

function series(symbol: "BTC-USD" | "ETH-USD", bars: BarResponse[], retrievedAt = "2026-11-08T04:36:00Z"): BarsResponse {
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
    last_close: bars.at(-1)?.close ?? null,
    previous_close: null,
    change: null,
    change_percent: null,
    retrieved_at: retrievedAt,
    source_url: null,
    bars,
  };
}

const btcBars = [
  bar(stamp(0), "8", "99", "1"),
  ...Array.from({ length: 19 }, (_, index) => bar(stamp(index + 1), "10", "40", "5")),
  bar(stamp(20), "30", "40", "5"),
];

const shortBars = [bar(stamp(0), "12", "13", "11"), bar(stamp(1), "13", "14", "12"), bar(stamp(2), "14", "15", "13")];

const ethBars = Array.from({ length: 20 }, (_, index) => bar(stamp(index), "2000", "2010", "1990"));

function renderQuant() {
  render(
    <MemoryRouter initialEntries={["/quant"]}>
      <AppRoutes />
    </MemoryRouter>,
  );
}

describe("quant page", () => {
  beforeEach(() => {
    vi.useRealTimers();
    vi.mocked(apiGet).mockReset();
    vi.mocked(apiPost).mockReset();
  });

  it("shows the 20-bar average and the distance from the last close", async () => {
    vi.mocked(apiGet).mockResolvedValue(series("BTC-USD", btcBars));
    renderQuant();

    expect(averageOfLastCloses(btcBars.map((item) => Number(item.close)))).toBe(11);
    expect(await screen.findByText("$11.00")).toBeInTheDocument();
    expect(screen.getByText("$30.00")).toBeInTheDocument();
    expect(screen.getByText("$99.00")).toBeInTheDocument();
    expect(screen.getByText("$1.00")).toBeInTheDocument();
    expect(screen.getByText("+$19.00")).toBeInTheDocument();
    expect(screen.getByText("+172.73% of the average")).toBeInTheDocument();
    expect(screen.getByText("Position in the window 29.59%.")).toBeInTheDocument();
    expect(screen.getByText("As of 2026-11-08T04:36:00Z")).toBeInTheDocument();
    expect(screen.getAllByText(/Not a trading signal/).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "BTC-USD" })).toHaveAttribute("aria-pressed", "true");
    expect(vi.mocked(apiGet)).toHaveBeenCalledWith("/api/v1/market/instruments/BTC-USD/bars?interval=1m&limit=180");
    expect(vi.mocked(apiPost)).not.toHaveBeenCalled();
  });

  it("says there are not enough bars for a short series", async () => {
    vi.mocked(apiGet).mockResolvedValue(series("BTC-USD", shortBars));
    renderQuant();

    expect(await screen.findByText("There are not enough bars for a 20-bar average.")).toBeInTheDocument();
    expect(screen.getByText("$14.00")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "20-bar average" })).not.toBeInTheDocument();
    expect(screen.queryByText(/Distance from the 20-bar average/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Position in the window/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Print minus average/)).not.toBeInTheDocument();
  });

  it("shows unavailable and drops a previous average when the candles fail", async () => {
    vi.useFakeTimers();
    let failed = false;
    vi.mocked(apiGet).mockImplementation(() =>
      failed ? Promise.reject(new Error("down")) : Promise.resolve(series("BTC-USD", btcBars)),
    );
    renderQuant();
    await act(async () => {
      await Promise.resolve();
    });

    expect(screen.getByText("$11.00")).toBeInTheDocument();
    failed = true;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(45_000);
    });

    expect(screen.getByRole("alert")).toHaveTextContent("1-minute candles are unavailable. No figures were invented.");
    expect(screen.queryByText("$11.00")).not.toBeInTheDocument();
    expect(screen.queryByText("$30.00")).not.toBeInTheDocument();
    expect(vi.mocked(apiPost)).not.toHaveBeenCalled();
  });

  it("replaces Bitcoin figures with the ETH-USD candles", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.includes("/ETH-USD/")) {
        return Promise.resolve(series("ETH-USD", ethBars, "2026-11-08T04:40:00Z"));
      }
      return Promise.resolve(series("BTC-USD", btcBars));
    });
    renderQuant();

    expect(await screen.findByText("$11.00")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "ETH-USD" }));

    expect(await screen.findAllByText("$2,000.00")).toHaveLength(2);
    expect(screen.queryByText("$11.00")).not.toBeInTheDocument();
    expect(screen.getByText("As of 2026-11-08T04:40:00Z")).toBeInTheDocument();
    expect(vi.mocked(apiGet)).toHaveBeenCalledWith("/api/v1/market/instruments/ETH-USD/bars?interval=1m&limit=180");
  });
});

const CANDLE_NOW = Date.parse("2026-11-08T05:00:00.000Z");

describe("quant candle age", () => {
  beforeEach(() => {
    vi.useRealTimers();
    vi.mocked(apiGet).mockReset();
    vi.mocked(apiPost).mockReset();
    vi.spyOn(Date, "now").mockReturnValue(CANDLE_NOW);
  });

  afterEach(() => {
    vi.mocked(Date.now).mockRestore();
  });

  function renderAged(start: string, close = "30.00") {
    vi.mocked(apiGet).mockResolvedValue(series("BTC-USD", [bar(start, close, close, close)]));
    renderQuant();
  }

  it("calls a bucket that started 30 seconds ago current and not stale", async () => {
    renderAged("2026-11-08T04:59:30Z");

    expect(await screen.findByText("Current 1-minute candle. 30 seconds left.")).toBeInTheDocument();
    expect(screen.getAllByText("$30.00").length).toBeGreaterThan(0);
    expect(screen.getByText("Bar start (UTC) 2026-11-08T04:59:30Z.")).toBeInTheDocument();
    expect(screen.getAllByText("Current 1-minute candle. 30 seconds left.").length).toBe(1);
    expect(screen.queryByText(/candle is stale/)).not.toBeInTheDocument();
    expect(
      screen.getByText("Candle time is the Coinbase bucket start. The close is not the live print. No order is sent."),
    ).toBeInTheDocument();
  });

  it("does not call a candle that closed 10 seconds ago stale", async () => {
    renderAged("2026-11-08T04:58:50Z");

    expect(await screen.findByText("Last 1-minute candle closed 10 seconds ago.")).toBeInTheDocument();
    expect(screen.getAllByText("$30.00").length).toBeGreaterThan(0);
    expect(screen.queryByText(/candle is stale/)).not.toBeInTheDocument();
  });

  it("keeps the close when the candle closed 91 seconds ago", async () => {
    renderAged("2026-11-08T04:57:29Z", "42.00");

    expect(await screen.findByText("1-minute candle is stale. Age 91 seconds.")).toBeInTheDocument();
    expect(screen.getAllByText("$42.00").length).toBeGreaterThan(0);
    expect(screen.queryByText(/Current 1-minute candle/)).not.toBeInTheDocument();
  });

  it("does not call an unreadable candle time current", async () => {
    renderAged("2026-11-08Tnot-readableZ", "14.00");

    expect(await screen.findByText("$14.00")).toBeInTheDocument();
    expect(screen.getByText("Candle time is unreadable.")).toBeInTheDocument();
    expect(screen.queryByText(/Current 1-minute candle/)).not.toBeInTheDocument();
  });
});

function quote(symbol: "BTC-USD" | "ETH-USD", price: string): TickerResponse {
  return {
    symbol,
    venue: "COINBASE",
    source_id: "coinbase-exchange",
    synthetic: false,
    price,
    bid: price,
    ask: price,
    size: "0.01",
    volume: "1",
    trade_time: "2026-11-08T05:00:00.000Z",
    trade_id: 1,
    retrieved_at: "2026-11-08T05:00:00Z",
    disclaimer: "Live print. No order is sent.",
  };
}

describe("quant print minus candle", () => {
  beforeEach(() => {
    vi.useRealTimers();
    vi.mocked(apiGet).mockReset();
    vi.mocked(apiPost).mockReset();
  });

  function renderGap(price: string, close: string | null) {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.includes("/ticker")) {
        return Promise.resolve(quote("BTC-USD", price));
      }
      if (close === null) {
        return Promise.reject(new Error("down"));
      }
      return Promise.resolve(series("BTC-USD", [bar(stamp(0), close, close, close)]));
    });
    renderQuant();
  }

  it("shows the print above the 1-minute close", async () => {
    renderGap("110.00", "100.00");

    expect(await screen.findByText("Print minus candle +$10.00 (+10.00%).")).toBeInTheDocument();
    expect(screen.getByText("Last trade $110.00.")).toBeInTheDocument();
    expect(screen.getAllByText("$100.00").length).toBeGreaterThan(0);
    expect(
      screen.getByText(
        "Last trade minus the latest 1-minute close. The close is not the live print. Not a trading signal. No order is sent.",
      ),
    ).toBeInTheDocument();
  });

  it("shows a zero gap when the print equals the close", async () => {
    renderGap("100.00", "100.00");

    expect(await screen.findByText("Print minus candle $0.00 (0.00%).")).toBeInTheDocument();
    expect(screen.getByText("Last trade $100.00.")).toBeInTheDocument();
  });

  it("shows the print below the 1-minute close", async () => {
    renderGap("90.00", "100.00");

    expect(await screen.findByText("Print minus candle -$10.00 (-10.00%).")).toBeInTheDocument();
    expect(screen.getByText("Last trade $90.00.")).toBeInTheDocument();
    expect(screen.getAllByText("$100.00").length).toBeGreaterThan(0);
  });

  it("does not invent a close when the candle is missing", async () => {
    renderGap("110.00", null);

    expect(await screen.findByText("Last trade $110.00.")).toBeInTheDocument();
    expect(screen.getByText("Print minus candle is unavailable.")).toBeInTheDocument();
    expect(screen.getByText("1-minute candles are unavailable. No figures were invented.")).toBeInTheDocument();
    expect(screen.queryByText("$100.00")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Last 1-minute close" })).not.toBeInTheDocument();
  });
});

describe("quant window position", () => {
  beforeEach(() => {
    vi.useRealTimers();
    vi.mocked(apiGet).mockReset();
    vi.mocked(apiPost).mockReset();
  });

  function renderWindow(close: string, high: string, low: string) {
    const bars = Array.from({ length: 20 }, (_, index) => bar(stamp(index), close, high, low));
    vi.mocked(apiGet).mockResolvedValue(series("BTC-USD", bars));
    renderQuant();
  }

  it("shows the close at the window low", async () => {
    renderWindow("50.00", "100.00", "50.00");

    expect(await screen.findByText("Position in the window 0.00%.")).toBeInTheDocument();
    expect(screen.getAllByText("$50.00").length).toBeGreaterThan(0);
    expect(screen.getByText("$100.00")).toBeInTheDocument();
    expect(screen.queryByText("Close is outside the window.")).not.toBeInTheDocument();
    expect(
      screen.getByText(
        "Share of the 1-minute window, from the low. Not a trading signal. The close is not the live print. No order is sent.",
      ),
    ).toBeInTheDocument();
  });

  it("shows the close at the window high", async () => {
    renderWindow("100.00", "100.00", "50.00");

    expect(await screen.findByText("Position in the window 100.00%.")).toBeInTheDocument();
    expect(screen.getByText("$50.00")).toBeInTheDocument();
    expect(screen.queryByText("Close is outside the window.")).not.toBeInTheDocument();
  });

  it("shows a close midway through the window", async () => {
    renderWindow("75.00", "100.00", "50.00");

    expect(await screen.findByText("Position in the window 50.00%.")).toBeInTheDocument();
    expect(screen.getAllByText("$75.00").length).toBeGreaterThan(0);
    expect(screen.getByText("$100.00")).toBeInTheDocument();
    expect(screen.getByText("$50.00")).toBeInTheDocument();
  });

  it("does not invent a percent for a flat window", async () => {
    renderWindow("40.00", "40.00", "40.00");

    expect(await screen.findByText("Position in the window is unavailable.")).toBeInTheDocument();
    expect(screen.getAllByText("$40.00").length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "20-bar average" })).toBeInTheDocument();
    expect(screen.queryByText(/Position in the window \d/)).not.toBeInTheDocument();
    expect(screen.queryByText("Close is outside the window.")).not.toBeInTheDocument();
  });
});

describe("quant print minus average", () => {
  beforeEach(() => {
    vi.useRealTimers();
    vi.mocked(apiGet).mockReset();
    vi.mocked(apiPost).mockReset();
  });

  function renderAverage(price: string | null, closes: string[]) {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.includes("/ticker")) {
        if (price === null) {
          return Promise.reject(new Error("down"));
        }
        return Promise.resolve(quote("BTC-USD", price));
      }
      return Promise.resolve(
        series(
          "BTC-USD",
          closes.map((close, index) => bar(stamp(index), close, close, close)),
        ),
      );
    });
    renderQuant();
  }

  it("shows the print above the 20-bar average", async () => {
    renderAverage("110.00", Array.from({ length: 20 }, () => "100.00"));

    expect(await screen.findByText("Print minus average +$10.00 (+10.00%).")).toBeInTheDocument();
    expect(screen.getByText("Last trade $110.00.")).toBeInTheDocument();
    expect(screen.getAllByText("$100.00").length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "20-bar average" })).toBeInTheDocument();
    expect(
      screen.getByText(
        "Last trade minus the 20-bar average of 1-minute closes. Not a trading signal. No order is sent.",
      ),
    ).toBeInTheDocument();
  });

  it("shows a zero gap when the print equals the average", async () => {
    renderAverage("100.00", Array.from({ length: 20 }, () => "100.00"));

    expect(await screen.findByText("Print minus average $0.00 (0.00%).")).toBeInTheDocument();
    expect(screen.getByText("Last trade $100.00.")).toBeInTheDocument();
  });

  it("shows the print below the 20-bar average", async () => {
    renderAverage("90.00", Array.from({ length: 20 }, () => "100.00"));

    expect(await screen.findByText("Print minus average -$10.00 (-10.00%).")).toBeInTheDocument();
    expect(screen.getByText("Last trade $90.00.")).toBeInTheDocument();
    expect(screen.getAllByText("$100.00").length).toBeGreaterThan(0);
  });

  it("does not invent an average when fewer than 20 bars are loaded", async () => {
    renderAverage("110.00", ["12.00", "13.00", "14.00"]);

    expect(await screen.findByText("Last trade $110.00.")).toBeInTheDocument();
    expect(screen.getByText("There are not enough bars for a 20-bar average.")).toBeInTheDocument();
    expect(screen.queryByText(/Print minus average/)).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "20-bar average" })).not.toBeInTheDocument();
    expect(screen.queryByText("$100.00")).not.toBeInTheDocument();
  });
});
