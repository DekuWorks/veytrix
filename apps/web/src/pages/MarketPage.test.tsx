import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CandlestickSeries, HistogramSeries, LineSeries } from "lightweight-charts";
import { apiGet } from "../api/client";
import type { BarResponse, BarsResponse, TickerResponse } from "../api/types";
import { AppRoutes } from "../App";
import { averageOfLastCloses } from "../quant/average";

const chartMock = vi.hoisted(() => {
  const recorded: { definition: { type: string }; data: unknown }[] = [];
  const priceLines: { price: number; title?: string; color?: string }[] = [];
  const addSeries = vi.fn((definition: { type: string }) => ({
    setData: (data: unknown) => {
      recorded.push({ definition, data });
    },
    createPriceLine: (options: { price: number; title?: string; color?: string }) => {
      const record = { ...options };
      const line = {
        record,
        applyOptions(next: Partial<typeof options>) {
          Object.assign(record, next);
        },
      };
      priceLines.push(record);
      return line;
    },
    applyOptions: () => undefined,
    removePriceLine: (line: { record: { price: number; title?: string; color?: string } }) => {
      const index = priceLines.indexOf(line.record);
      if (index >= 0) {
        priceLines.splice(index, 1);
      }
    },
  }));
  return { recorded, addSeries, priceLines };
});

vi.mock("../api/client", () => ({
  apiGet: vi.fn(),
}));

vi.mock("lightweight-charts", () => ({
  CandlestickSeries: { type: "Candlestick" },
  LineSeries: { type: "Line" },
  ColorType: { Solid: "solid" },
  HistogramSeries: { type: "Histogram" },
  LineStyle: { Solid: 0, Dotted: 1, Dashed: 2, LargeDashed: 3 },
  createChart: () => ({
    addSeries: chartMock.addSeries,
    remove: () => {
      chartMock.priceLines.length = 0;
    },
    timeScale: () => ({ fitContent: () => undefined }),
    panes: () => [{ setStretchFactor: () => undefined }, { setStretchFactor: () => undefined }],
  }),
}));

const intraday: BarsResponse = {
  symbol: "BTC-USD",
  venue: "COINBASE",
  asset_type: "crypto",
  currency: "USD",
  source_id: "coinbase-exchange",
  interval: "1m",
  seed: null,
  synthetic: false,
  calendar_note: "Each bar is one Coinbase minute in UTC.",
  disclaimer:
    "BTC-USD 1-minute candles from Coinbase. Not a consolidated quote. Not investment advice. No order is sent.",
  last_close: "75805.98",
  previous_close: "75800.00",
  change: "+5.98",
  change_percent: "+0.01",
  retrieved_at: "2026-11-08T03:59:08Z",
  source_url: "https://api.exchange.coinbase.com/products/BTC-USD/candles",
  bars: [
    {
      bar_start: "2026-11-08T03:58:00Z",
      open: "75800.00",
      high: "75810.00",
      low: "75790.00",
      close: "75802.00",
      volume: "1.25",
    },
    {
      bar_start: "2026-11-08T03:59:00Z",
      open: "75802.00",
      high: "75820.00",
      low: "75795.00",
      close: "75805.98",
      volume: "2.5",
    },
  ],
};

const quote: BarsResponse = {
  symbol: "BTC-USD",
  venue: "COINBASE",
  asset_type: "crypto",
  currency: "USD",
  source_id: "coinbase-exchange",
  interval: "1d",
  seed: null,
  synthetic: false,
  calendar_note: "Coinbase daily buckets start at 00:00 UTC.",
  disclaimer: "Personal research display. Not investment advice.",
  last_close: "75767.33",
  previous_close: "75000.00",
  change: "+767.33",
  change_percent: "+1.02",
  retrieved_at: "2026-11-08T03:00:00Z",
  source_url: "https://api.exchange.coinbase.com/products/BTC-USD/candles",
  bars: [
    {
      bar_start: "2026-11-08T00:00:00Z",
      open: "75753.95",
      high: "75830.11",
      low: "75545.34",
      close: "75767.33",
      volume: "260.19458529",
    },
  ],
};

const ticker: TickerResponse = {
  symbol: "BTC-USD",
  venue: "COINBASE",
  source_id: "coinbase-exchange",
  synthetic: false,
  price: "75764.49",
  bid: "75764.49",
  ask: "75764.50",
  size: "0.00000011",
  volume: "2022.50285353",
  trade_time: "2026-11-08T03:55:44.792670175Z",
  trade_id: 1116967290,
  retrieved_at: "2026-11-08T03:55:45Z",
  disclaimer: "Live print. Not investment advice. No order is sent.",
};

function minuteBars(count: number, closes: readonly string[]): BarResponse[] {
  return closes.slice(0, count).map((close, index) => {
    const minute = String(index).padStart(2, "0");
    return {
      bar_start: `2026-11-08T04:${minute}:00Z`,
      open: close,
      high: close,
      low: close,
      close,
      volume: "1",
    };
  });
}

describe("market page", () => {
  beforeEach(() => {
    chartMock.addSeries.mockClear();
    chartMock.recorded.length = 0;
    chartMock.priceLines.length = 0;
    vi.mocked(apiGet).mockReset();
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.includes("/ticker")) {
        return Promise.resolve(ticker);
      }
      if (path.includes("interval=1m")) {
        return Promise.resolve(intraday);
      }
      if (path.includes("interval=1d")) {
        return Promise.resolve(quote);
      }
      return Promise.reject(new Error(`unexpected ${path}`));
    });
  });

  it("shows an error instead of invented prices", async () => {
    vi.mocked(apiGet).mockRejectedValue(new Error("offline"));

    render(
      <MemoryRouter initialEntries={["/market"]}>
        <AppRoutes />
      </MemoryRouter>,
    );

    const alerts = await screen.findAllByRole("alert");
    expect(alerts.some((node) => /unavailable/i.test(node.textContent ?? ""))).toBe(true);
    expect(screen.queryByRole("img", { name: /candlestick/i })).not.toBeInTheDocument();
    expect(chartMock.addSeries).not.toHaveBeenCalled();
  });

  it("renders the Coinbase close instead of the synthetic series", async () => {
    render(
      <MemoryRouter initialEntries={["/market"]}>
        <AppRoutes />
      </MemoryRouter>,
    );

    expect((await screen.findAllByText("$75,764.49")).length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "BTC-USD · 1 minute" })).toBeInTheDocument();
    expect(screen.getByText("$75,805.98")).toBeInTheDocument();
    expect(screen.getAllByText(/As of 2026-11-08T03:59:08Z/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/No order is sent/).length).toBeGreaterThan(0);
    expect(
      screen.getByRole("img", {
        name: /1-minute candlestick chart from Coinbase/i,
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("$75,767.33")).toBeInTheDocument();
    expect(screen.getByText(/\+\$767\.33/)).toBeInTheDocument();
    expect(screen.getByText("+1.02%")).toBeInTheDocument();
    expect(screen.queryByText(/synthetic sample/i)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "BTC-USD" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "ETH-USD" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("button", { name: "SOL-USD" })).toHaveAttribute("aria-pressed", "false");
    const paths = vi.mocked(apiGet).mock.calls.map(([path]) => path);
    expect(paths.every((path) => path.includes("/BTC-USD/"))).toBe(true);
    expect(paths.some((path) => path.includes("interval=1m"))).toBe(true);
    expect(paths.some((path) => path.includes("interval=1d"))).toBe(true);
  });

  it("switches the headline, chart, and daily table to ETH-USD", async () => {
    const ethTicker: TickerResponse = {
      ...ticker,
      symbol: "ETH-USD",
      price: "3210.55",
      bid: "3210.50",
      ask: "3210.60",
      volume: "12345.6",
      trade_time: "2026-11-08T04:11:59.100000Z",
      disclaimer: "Live ETH-USD last trade from Coinbase. Not a consolidated quote. Not investment advice. No order is sent.",
    };
    const ethIntraday: BarsResponse = {
      ...intraday,
      symbol: "ETH-USD",
      last_close: "3208.10",
      retrieved_at: "2026-11-08T04:12:00Z",
      source_url: "https://api.exchange.coinbase.com/products/ETH-USD/candles",
      disclaimer:
        "ETH-USD 1-minute candles from Coinbase. Not a consolidated quote. Not investment advice. No order is sent.",
      bars: [
        {
          bar_start: "2026-11-08T04:11:00Z",
          open: "3208.00",
          high: "3212.00",
          low: "3206.00",
          close: "3208.10",
          volume: "12.5",
        },
      ],
    };
    const ethDaily: BarsResponse = {
      ...quote,
      symbol: "ETH-USD",
      last_close: "3180.00",
      previous_close: "3160.00",
      change: "+20.00",
      change_percent: "+0.63",
      retrieved_at: "2026-11-08T04:12:00Z",
      source_url: "https://api.exchange.coinbase.com/products/ETH-USD/candles",
      disclaimer:
        "ETH-USD daily candles from Coinbase. Not a consolidated quote. Not investment advice. No order is sent.",
      bars: [
        {
          bar_start: "2026-11-08T00:00:00Z",
          open: "3160.00",
          high: "3250.00",
          low: "3150.10",
          close: "3180.00",
          volume: "980.25",
        },
      ],
    };
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.includes("/ETH-USD/ticker")) {
        return Promise.resolve(ethTicker);
      }
      if (path.includes("/ETH-USD/") && path.includes("interval=1m")) {
        return Promise.resolve(ethIntraday);
      }
      if (path.includes("/ETH-USD/") && path.includes("interval=1d")) {
        return Promise.resolve(ethDaily);
      }
      if (path.includes("/ticker")) {
        return Promise.resolve(ticker);
      }
      if (path.includes("interval=1m")) {
        return Promise.resolve(intraday);
      }
      if (path.includes("interval=1d")) {
        return Promise.resolve(quote);
      }
      return Promise.reject(new Error(`unexpected ${path}`));
    });

    render(
      <MemoryRouter initialEntries={["/market"]}>
        <AppRoutes />
      </MemoryRouter>,
    );

    expect((await screen.findAllByText("$75,764.49")).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "ETH-USD" }));

    expect((await screen.findAllByText("$3,210.55")).length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "ETH-USD · 1 minute" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Live print · ETH-USD" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Daily candles · ETH-USD" })).toBeInTheDocument();
    expect(screen.getByText("$3,208.10")).toBeInTheDocument();
    expect(screen.getAllByText(/As of 2026-11-08T04:12:00Z/).length).toBeGreaterThan(0);
    expect(screen.getByText("Exchange time 2026-11-08T04:11:59.100000Z")).toBeInTheDocument();
    expect(screen.getByText("$3,180.00")).toBeInTheDocument();
    expect(screen.getAllByText(/No order is sent/).length).toBeGreaterThan(0);
    expect(
      screen.getByRole("img", {
        name: /ETH-USD 1-minute candlestick chart from Coinbase/i,
      }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "BTC-USD · 1 minute" })).not.toBeInTheDocument();
    expect(screen.queryByText("$75,764.49")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "ETH-USD" })).toHaveAttribute("aria-pressed", "true");
    const paths = vi.mocked(apiGet).mock.calls.map(([path]) => path);
    expect(paths.some((path) => path.includes("/ETH-USD/ticker"))).toBe(true);
    expect(paths.some((path) => path.includes("/ETH-USD/bars?interval=1m"))).toBe(true);
    expect(paths.some((path) => path.includes("/ETH-USD/bars?interval=1d"))).toBe(true);
  });

  it("plots the shared 20-bar average from the 20th close onward", async () => {
    const closes = ["1", ...Array.from({ length: 20 }, () => "10")];
    const bars = minuteBars(closes.length, closes);
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.includes("/ticker")) {
        return Promise.resolve(ticker);
      }
      if (path.includes("interval=1m")) {
        return Promise.resolve({ ...intraday, last_close: "10", bars });
      }
      if (path.includes("interval=1d")) {
        return Promise.resolve(quote);
      }
      return Promise.reject(new Error(`unexpected ${path}`));
    });

    render(
      <MemoryRouter initialEntries={["/market"]}>
        <AppRoutes />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("img", { name: /candlestick/i })).toBeInTheDocument();
    const line = chartMock.recorded.filter((item) => item.definition === LineSeries);
    const candles = chartMock.recorded.filter((item) => item.definition === CandlestickSeries);
    expect(candles.length).toBeGreaterThan(0);
    expect(line).toHaveLength(1);
    const points = line[0]?.data as { value: number }[];
    expect(points).toHaveLength(closes.length - 19);
    expect(points.at(-1)?.value).toBe(averageOfLastCloses(closes.map(Number)));
    expect(chartMock.addSeries).toHaveBeenCalledWith(LineSeries, expect.anything());
  });

  it("draws candles and no average line for 19 bars", async () => {
    const closes = Array.from({ length: 19 }, () => "10");
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.includes("/ticker")) {
        return Promise.resolve(ticker);
      }
      if (path.includes("interval=1m")) {
        return Promise.resolve({ ...intraday, last_close: "10", bars: minuteBars(19, closes) });
      }
      if (path.includes("interval=1d")) {
        return Promise.resolve(quote);
      }
      return Promise.reject(new Error(`unexpected ${path}`));
    });

    render(
      <MemoryRouter initialEntries={["/market"]}>
        <AppRoutes />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("img", { name: /candlestick/i })).toBeInTheDocument();
    const candles = chartMock.recorded.find((item) => item.definition === CandlestickSeries);
    expect(candles?.data).toHaveLength(19);
    expect(chartMock.recorded.some((item) => item.definition === LineSeries)).toBe(false);
    expect(chartMock.addSeries).not.toHaveBeenCalledWith(LineSeries, expect.anything());
  });

  it("plots base volume and omits a missing volume without dropping zero", async () => {
    const bars: BarResponse[] = [
      {
        bar_start: "2026-11-08T04:00:00Z",
        open: "10",
        high: "12",
        low: "10",
        close: "12",
        volume: "1.5",
      },
      {
        bar_start: "2026-11-08T04:01:00Z",
        open: "12",
        high: "12",
        low: "11",
        close: "11",
        volume: "",
      },
      {
        bar_start: "2026-11-08T04:02:00Z",
        open: "11",
        high: "11",
        low: "11",
        close: "11",
        volume: "0",
      },
      {
        bar_start: "2026-11-08T04:03:00Z",
        open: "11",
        high: "11",
        low: "10",
        close: "10",
        volume: "-1",
      },
      {
        bar_start: "2026-11-08T04:04:00Z",
        open: "10",
        high: "10",
        low: "9",
        close: "9",
        volume: "nope",
      },
    ];
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.includes("/ticker")) {
        return Promise.resolve(ticker);
      }
      if (path.includes("interval=1m")) {
        return Promise.resolve({ ...intraday, bars });
      }
      if (path.includes("interval=1d")) {
        return Promise.resolve(quote);
      }
      return Promise.reject(new Error(`unexpected ${path}`));
    });

    render(
      <MemoryRouter initialEntries={["/market"]}>
        <AppRoutes />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("img", { name: /candlestick/i })).toBeInTheDocument();
    await waitFor(() => {
      const histogram = chartMock.recorded.find((item) => item.definition === HistogramSeries);
      const candles = chartMock.recorded.find((item) => item.definition === CandlestickSeries);
      expect(candles?.data).toHaveLength(5);
      expect(histogram?.data).toEqual([
        { time: Date.parse("2026-11-08T04:00:00Z") / 1000, value: 1.5, color: "#3dbe8b" },
        { time: Date.parse("2026-11-08T04:02:00Z") / 1000, value: 0, color: "#e07a7a" },
      ]);
    });
    expect(chartMock.addSeries).toHaveBeenCalledWith(HistogramSeries, expect.anything(), 1);
    expect(vi.mocked(apiGet).mock.calls.some(([path]) => path.includes("/risk/"))).toBe(false);
  });

  it("draws one last-trade line at the print, not the candle close", async () => {
    render(
      <MemoryRouter initialEntries={["/market"]}>
        <AppRoutes />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("img", { name: /candlestick/i })).toBeInTheDocument();
    expect(chartMock.priceLines.filter((line) => line.title === "Last trade")).toEqual([
      expect.objectContaining({ price: 75764.49, title: "Last trade", color: "#7aa2ff" }),
    ]);
    expect(chartMock.priceLines.some((line) => line.price === 75805.98)).toBe(false);
  });

  it("does not draw a line from the candle close when the print is missing", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.includes("/ticker")) {
        return Promise.resolve({ ...ticker, price: "" });
      }
      if (path.includes("interval=1m")) {
        return Promise.resolve(intraday);
      }
      if (path.includes("interval=1d")) {
        return Promise.resolve(quote);
      }
      return Promise.reject(new Error(`unexpected ${path}`));
    });

    render(
      <MemoryRouter initialEntries={["/market"]}>
        <AppRoutes />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("img", { name: /candlestick/i })).toBeInTheDocument();
    expect(screen.getByText("$75,805.98")).toBeInTheDocument();
    expect(chartMock.priceLines.filter((line) => line.title === "Last trade")).toEqual([]);
    expect(chartMock.priceLines.some((line) => line.price === 75805.98)).toBe(false);
  });

  it("does not keep the previous product's last-trade line", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.includes("/ETH-USD/ticker")) {
        return Promise.resolve(ethTickerPrint);
      }
      if (path.includes("/ETH-USD/") && path.includes("interval=1m")) {
        return Promise.resolve(ethMinute);
      }
      if (path.includes("/ETH-USD/") && path.includes("interval=1d")) {
        return Promise.resolve(ethDailyPrint);
      }
      if (path.includes("/ticker")) {
        return Promise.resolve(ticker);
      }
      if (path.includes("interval=1m")) {
        return Promise.resolve(intraday);
      }
      if (path.includes("interval=1d")) {
        return Promise.resolve(quote);
      }
      return Promise.reject(new Error(`unexpected ${path}`));
    });

    render(
      <MemoryRouter initialEntries={["/market"]}>
        <AppRoutes />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("img", { name: /BTC-USD 1-minute candlestick chart/i })).toBeInTheDocument();
    expect(chartMock.priceLines.filter((line) => line.title === "Last trade")).toEqual([
      expect.objectContaining({ price: 75764.49, title: "Last trade" }),
    ]);
    fireEvent.click(screen.getByRole("button", { name: "ETH-USD" }));

    expect(await screen.findByRole("img", { name: /ETH-USD 1-minute candlestick chart/i })).toBeInTheDocument();
    expect(chartMock.priceLines.filter((line) => line.title === "Last trade")).toEqual([
      expect.objectContaining({ price: 2230.1, title: "Last trade" }),
    ]);
    expect(chartMock.priceLines.some((line) => line.price === 75764.49)).toBe(false);
    expect(chartMock.priceLines.some((line) => line.price === 2231.49)).toBe(false);
  });

  it("draws the previous daily close on its own line", async () => {
    render(
      <MemoryRouter initialEntries={["/market"]}>
        <AppRoutes />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("img", { name: /candlestick/i })).toBeInTheDocument();
    expect(chartMock.priceLines.filter((line) => line.title === "Previous close")).toEqual([
      expect.objectContaining({ price: 75000, title: "Previous close", color: "#e36ad4" }),
    ]);
    expect(chartMock.priceLines.filter((line) => line.title === "Last trade")).toEqual([
      expect.objectContaining({ price: 75764.49, title: "Last trade" }),
    ]);
    expect(chartMock.priceLines.some((line) => line.price === 75767.33)).toBe(false);
    expect(chartMock.priceLines.some((line) => line.price === 75805.98)).toBe(false);
  });

  it("does not draw today's close when the previous close is missing", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.includes("/ticker")) {
        return Promise.resolve(ticker);
      }
      if (path.includes("interval=1m")) {
        return Promise.resolve(intraday);
      }
      if (path.includes("interval=1d")) {
        return Promise.resolve({ ...quote, previous_close: null });
      }
      return Promise.reject(new Error(`unexpected ${path}`));
    });

    render(
      <MemoryRouter initialEntries={["/market"]}>
        <AppRoutes />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("img", { name: /candlestick/i })).toBeInTheDocument();
    expect(screen.getByText("$75,767.33")).toBeInTheDocument();
    expect(chartMock.priceLines.filter((line) => line.title === "Previous close")).toEqual([]);
    expect(chartMock.priceLines.some((line) => line.price === 75767.33)).toBe(false);
    expect(chartMock.priceLines.filter((line) => line.title === "Last trade")).toEqual([
      expect.objectContaining({ price: 75764.49, title: "Last trade" }),
    ]);
  });

  it("does not keep the previous product's daily close", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.includes("/ETH-USD/ticker")) {
        return Promise.resolve(ethTickerPrint);
      }
      if (path.includes("/ETH-USD/") && path.includes("interval=1m")) {
        return Promise.resolve(ethMinute);
      }
      if (path.includes("/ETH-USD/") && path.includes("interval=1d")) {
        return Promise.resolve({ ...ethDailyPrint, previous_close: "2100.00", last_close: "2231.82" });
      }
      if (path.includes("/ticker")) {
        return Promise.resolve(ticker);
      }
      if (path.includes("interval=1m")) {
        return Promise.resolve(intraday);
      }
      if (path.includes("interval=1d")) {
        return Promise.resolve(quote);
      }
      return Promise.reject(new Error(`unexpected ${path}`));
    });

    render(
      <MemoryRouter initialEntries={["/market"]}>
        <AppRoutes />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("img", { name: /BTC-USD 1-minute candlestick chart/i })).toBeInTheDocument();
    await waitFor(() => {
      expect(chartMock.priceLines.filter((line) => line.title === "Previous close")).toEqual([
        expect.objectContaining({ price: 75000, title: "Previous close" }),
      ]);
    });
    fireEvent.click(screen.getByRole("button", { name: "ETH-USD" }));

    expect(await screen.findByRole("img", { name: /ETH-USD 1-minute candlestick chart/i })).toBeInTheDocument();
    await waitFor(() => {
      expect(chartMock.priceLines.filter((line) => line.title === "Previous close")).toEqual([
        expect.objectContaining({ price: 2100, title: "Previous close" }),
      ]);
    });
    expect(chartMock.priceLines.some((line) => line.price === 75000)).toBe(false);
    expect(chartMock.priceLines.some((line) => line.price === 2231.82)).toBe(false);
    expect(chartMock.priceLines.filter((line) => line.title === "Last trade")).toEqual([
      expect.objectContaining({ price: 2230.1, title: "Last trade" }),
    ]);
  });

  it("draws the in-progress day's high and low, not the previous day", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.includes("/ticker")) {
        return Promise.resolve(ticker);
      }
      if (path.includes("interval=1m")) {
        return Promise.resolve(intraday);
      }
      if (path.includes("interval=1d")) {
        return Promise.resolve({
          ...quote,
          bars: [
            {
              ...quote.bars[0],
              bar_start: "2026-11-07T00:00:00Z",
              high: "70000.00",
              low: "69000.00",
              close: "69500.00",
            },
            quote.bars[0],
          ],
        });
      }
      return Promise.reject(new Error(`unexpected ${path}`));
    });

    render(
      <MemoryRouter initialEntries={["/market"]}>
        <AppRoutes />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("img", { name: /candlestick/i })).toBeInTheDocument();
    expect(chartMock.priceLines.filter((line) => line.title === "Day high")).toEqual([
      expect.objectContaining({ price: 75830.11, title: "Day high", color: "#f97316" }),
    ]);
    expect(chartMock.priceLines.filter((line) => line.title === "Day low")).toEqual([
      expect.objectContaining({ price: 75545.34, title: "Day low", color: "#22d3ee" }),
    ]);
    expect(chartMock.priceLines.some((line) => line.price === 70000 || line.price === 69000)).toBe(false);
    expect(chartMock.priceLines.some((line) => line.price === 75810 || line.price === 75790)).toBe(false);
    expect(chartMock.priceLines.filter((line) => line.title === "Last trade")).toEqual([
      expect.objectContaining({ price: 75764.49, title: "Last trade" }),
    ]);
    expect(chartMock.priceLines.filter((line) => line.title === "Previous close")).toEqual([
      expect.objectContaining({ price: 75000, title: "Previous close" }),
    ]);
  });

  it("removes only the day-low line when the low is missing", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.includes("/ticker")) {
        return Promise.resolve(ticker);
      }
      if (path.includes("interval=1m")) {
        return Promise.resolve(intraday);
      }
      if (path.includes("interval=1d")) {
        return Promise.resolve({
          ...quote,
          bars: [{ ...quote.bars[0], low: "" }],
        });
      }
      return Promise.reject(new Error(`unexpected ${path}`));
    });

    render(
      <MemoryRouter initialEntries={["/market"]}>
        <AppRoutes />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("img", { name: /candlestick/i })).toBeInTheDocument();
    expect(chartMock.priceLines.filter((line) => line.title === "Day high")).toEqual([
      expect.objectContaining({ price: 75830.11, title: "Day high" }),
    ]);
    expect(chartMock.priceLines.filter((line) => line.title === "Day low")).toEqual([]);
    expect(chartMock.priceLines.filter((line) => line.title === "Last trade")).toHaveLength(1);
    expect(chartMock.priceLines.filter((line) => line.title === "Previous close")).toHaveLength(1);
  });

  it("draws neither day line when the high is below the low", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.includes("/ticker")) {
        return Promise.resolve(ticker);
      }
      if (path.includes("interval=1m")) {
        return Promise.resolve(intraday);
      }
      if (path.includes("interval=1d")) {
        return Promise.resolve({
          ...quote,
          bars: [{ ...quote.bars[0], high: "100.00", low: "200.00" }],
        });
      }
      return Promise.reject(new Error(`unexpected ${path}`));
    });

    render(
      <MemoryRouter initialEntries={["/market"]}>
        <AppRoutes />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("img", { name: /candlestick/i })).toBeInTheDocument();
    expect(chartMock.priceLines.filter((line) => line.title === "Day high" || line.title === "Day low")).toEqual(
      [],
    );
    expect(chartMock.priceLines.some((line) => line.price === 100 || line.price === 200)).toBe(false);
    expect(chartMock.priceLines.filter((line) => line.title === "Last trade")).toEqual([
      expect.objectContaining({ price: 75764.49, title: "Last trade" }),
    ]);
    expect(chartMock.priceLines.filter((line) => line.title === "Previous close")).toEqual([
      expect.objectContaining({ price: 75000, title: "Previous close" }),
    ]);
  });

  it("draws both day lines on a flat daily candle", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.includes("/ticker")) {
        return Promise.resolve(ticker);
      }
      if (path.includes("interval=1m")) {
        return Promise.resolve(intraday);
      }
      if (path.includes("interval=1d")) {
        return Promise.resolve({
          ...quote,
          bars: [{ ...quote.bars[0], high: "100.50", low: "100.50" }],
        });
      }
      return Promise.reject(new Error(`unexpected ${path}`));
    });

    render(
      <MemoryRouter initialEntries={["/market"]}>
        <AppRoutes />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("img", { name: /candlestick/i })).toBeInTheDocument();
    expect(chartMock.priceLines.filter((line) => line.title === "Day high")).toEqual([
      expect.objectContaining({ price: 100.5, title: "Day high", color: "#f97316" }),
    ]);
    expect(chartMock.priceLines.filter((line) => line.title === "Day low")).toEqual([
      expect.objectContaining({ price: 100.5, title: "Day low", color: "#22d3ee" }),
    ]);
  });

  it("does not keep the previous product's day high or low", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.includes("/ETH-USD/ticker")) {
        return Promise.resolve(ethTickerPrint);
      }
      if (path.includes("/ETH-USD/") && path.includes("interval=1m")) {
        return Promise.resolve(ethMinute);
      }
      if (path.includes("/ETH-USD/") && path.includes("interval=1d")) {
        return Promise.resolve({
          ...ethDailyPrint,
          previous_close: "2100.00",
          bars: [
            {
              ...quote.bars[0],
              bar_start: "2026-11-07T00:00:00Z",
              high: "2400.00",
              low: "2100.00",
              close: "2200.00",
            },
            {
              ...quote.bars[0],
              bar_start: "2026-11-08T00:00:00Z",
              high: "2300.00",
              low: "2200.00",
              close: "2231.82",
            },
          ],
        });
      }
      if (path.includes("/ticker")) {
        return Promise.resolve(ticker);
      }
      if (path.includes("interval=1m")) {
        return Promise.resolve(intraday);
      }
      if (path.includes("interval=1d")) {
        return Promise.resolve(quote);
      }
      return Promise.reject(new Error(`unexpected ${path}`));
    });

    render(
      <MemoryRouter initialEntries={["/market"]}>
        <AppRoutes />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("img", { name: /BTC-USD 1-minute candlestick chart/i })).toBeInTheDocument();
    expect(chartMock.priceLines.filter((line) => line.title === "Day high")).toEqual([
      expect.objectContaining({ price: 75830.11, title: "Day high" }),
    ]);
    expect(chartMock.priceLines.filter((line) => line.title === "Day low")).toEqual([
      expect.objectContaining({ price: 75545.34, title: "Day low" }),
    ]);
    fireEvent.click(screen.getByRole("button", { name: "ETH-USD" }));

    expect(await screen.findByRole("img", { name: /ETH-USD 1-minute candlestick chart/i })).toBeInTheDocument();
    expect(chartMock.priceLines.filter((line) => line.title === "Day high")).toEqual([
      expect.objectContaining({ price: 2300, title: "Day high" }),
    ]);
    expect(chartMock.priceLines.filter((line) => line.title === "Day low")).toEqual([
      expect.objectContaining({ price: 2200, title: "Day low" }),
    ]);
    expect(chartMock.priceLines.some((line) => line.price === 75830.11 || line.price === 75545.34)).toBe(false);
    expect(chartMock.priceLines.some((line) => line.title !== "Previous close" && line.price === 2100)).toBe(false);
    expect(chartMock.priceLines.some((line) => line.price === 2400)).toBe(false);
    expect(chartMock.priceLines.filter((line) => line.title === "Last trade")).toEqual([
      expect.objectContaining({ price: 2230.1, title: "Last trade" }),
    ]);
    expect(chartMock.priceLines.filter((line) => line.title === "Previous close")).toEqual([
      expect.objectContaining({ price: 2100, title: "Previous close" }),
    ]);
  });

  it("removes the previous-close line when the daily fetch fails", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.includes("/ticker")) {
        return Promise.resolve(ticker);
      }
      if (path.includes("interval=1m")) {
        return Promise.resolve(intraday);
      }
      return Promise.reject(new Error("daily down"));
    });

    render(
      <MemoryRouter initialEntries={["/market"]}>
        <AppRoutes />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("img", { name: /candlestick/i })).toBeInTheDocument();
    expect(screen.getByText("Daily candles are unavailable. No price was invented.")).toBeInTheDocument();
    expect(chartMock.priceLines.filter((line) => line.title === "Previous close")).toEqual([]);
    expect(chartMock.priceLines.filter((line) => line.title === "Day high")).toEqual([]);
    expect(chartMock.priceLines.filter((line) => line.title === "Day low")).toEqual([]);
    expect(chartMock.priceLines.filter((line) => line.title === "Last trade")).toEqual([
      expect.objectContaining({ price: 75764.49, title: "Last trade" }),
    ]);
  });

  it("drops the day lines after a failed daily refresh and keeps the previous close", async () => {
    const dailyLoads: Array<() => void> = [];
    const original = window.setInterval.bind(window);
    const spy = vi.spyOn(window, "setInterval").mockImplementation((handler, timeout, ...rest) => {
      if (timeout === 15 * 60_000 && typeof handler === "function") {
        dailyLoads.push(handler as () => void);
        return 0;
      }
      return original(handler, timeout, ...rest);
    });
    try {
      render(
        <MemoryRouter initialEntries={["/market"]}>
          <AppRoutes />
        </MemoryRouter>,
      );

      expect(await screen.findByRole("img", { name: /candlestick/i })).toBeInTheDocument();
      expect(chartMock.priceLines.filter((line) => line.title === "Day high")).toEqual([
        expect.objectContaining({ price: 75830.11, title: "Day high" }),
      ]);
      expect(chartMock.priceLines.filter((line) => line.title === "Previous close")).toEqual([
        expect.objectContaining({ price: 75000, title: "Previous close" }),
      ]);

      vi.mocked(apiGet).mockImplementation((path: string) => {
        if (path.includes("/ticker")) {
          return Promise.resolve(ticker);
        }
        if (path.includes("interval=1m")) {
          return Promise.resolve(intraday);
        }
        return Promise.reject(new Error("daily down"));
      });
      await act(async () => {
        dailyLoads[0]?.();
      });

      await waitFor(() => {
        expect(chartMock.priceLines.filter((line) => line.title === "Day high")).toEqual([]);
        expect(chartMock.priceLines.filter((line) => line.title === "Day low")).toEqual([]);
      });
      expect(screen.getByRole("img", { name: /candlestick/i })).toBeInTheDocument();
      expect(chartMock.priceLines.filter((line) => line.title === "Previous close")).toEqual([
        expect.objectContaining({ price: 75000, title: "Previous close" }),
      ]);
      expect(chartMock.priceLines.filter((line) => line.title === "Last trade")).toEqual([
        expect.objectContaining({ price: 75764.49, title: "Last trade" }),
      ]);
    } finally {
      spy.mockRestore();
    }
  });

  it("ignores a rejection from the product that is no longer selected", async () => {
    let rejectBtcMinute: ((reason: Error) => void) | undefined;
    let btcMinuteCalls = 0;
    let ethMinuteCalls = 0;
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.includes("/BTC-USD/") && path.includes("interval=1m")) {
        btcMinuteCalls += 1;
        return new Promise((_resolve, reject) => {
          rejectBtcMinute = reject;
        });
      }
      if (path.includes("/ETH-USD/") && path.includes("interval=1m")) {
        ethMinuteCalls += 1;
        return Promise.resolve(ethMinute);
      }
      if (path.includes("/ETH-USD/ticker")) {
        return Promise.resolve(ethTickerPrint);
      }
      if (path.includes("/ticker")) {
        return Promise.resolve(ticker);
      }
      if (path.includes("/ETH-USD/") && path.includes("interval=1d")) {
        return Promise.resolve(ethDailyPrint);
      }
      if (path.includes("interval=1d")) {
        return Promise.resolve(quote);
      }
      return Promise.reject(new Error(`unexpected ${path}`));
    });

    render(
      <MemoryRouter initialEntries={["/market"]}>
        <AppRoutes />
      </MemoryRouter>,
    );

    expect((await screen.findAllByText("$75,764.49")).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "ETH-USD" }));
    expect((await screen.findAllByText("$2,231.49")).length).toBeGreaterThan(0);

    await act(async () => {
      rejectBtcMinute?.(new Error("superseded"));
    });

    expect(screen.queryByText("1-minute candles are unavailable. No price was invented.")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "ETH-USD · 1 minute" })).toBeInTheDocument();
    expect(screen.getAllByText("$2,231.49").length).toBeGreaterThan(0);
    expect(btcMinuteCalls).toBe(1);
    expect(ethMinuteCalls).toBe(1);
  });

  it("shows candles after one failure and a successful retry", async () => {
    let ethMinuteCalls = 0;
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.includes("/ETH-USD/") && path.includes("interval=1m")) {
        ethMinuteCalls += 1;
        if (ethMinuteCalls === 1) {
          return Promise.reject(new Error("limit"));
        }
        return Promise.resolve(ethMinute);
      }
      if (path.includes("/ETH-USD/ticker")) {
        return Promise.resolve(ethTickerPrint);
      }
      if (path.includes("/ETH-USD/") && path.includes("interval=1d")) {
        return Promise.resolve(ethDailyPrint);
      }
      if (path.includes("/ticker")) {
        return Promise.resolve(ticker);
      }
      if (path.includes("interval=1m")) {
        return Promise.resolve(intraday);
      }
      if (path.includes("interval=1d")) {
        return Promise.resolve(quote);
      }
      return Promise.reject(new Error(`unexpected ${path}`));
    });

    render(
      <MemoryRouter initialEntries={["/market"]}>
        <AppRoutes />
      </MemoryRouter>,
    );

    expect(await screen.findByText("$75,805.98")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "ETH-USD" }));

    expect(await screen.findByText("$2,231.49")).toBeInTheDocument();
    expect(screen.queryByText("1-minute candles are unavailable. No price was invented.")).not.toBeInTheDocument();
    expect(screen.getByRole("img", { name: /ETH-USD 1-minute candlestick chart/i })).toBeInTheDocument();
    expect(ethMinuteCalls).toBe(2);
  });

  it("shows the unavailable copy after two candle failures", async () => {
    let ethMinuteCalls = 0;
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.includes("/ETH-USD/") && path.includes("interval=1m")) {
        ethMinuteCalls += 1;
        return Promise.reject(new Error("limit"));
      }
      if (path.includes("/ETH-USD/ticker")) {
        return Promise.resolve(ethTickerPrint);
      }
      if (path.includes("/ETH-USD/") && path.includes("interval=1d")) {
        return Promise.resolve(ethDailyPrint);
      }
      if (path.includes("/ticker")) {
        return Promise.resolve(ticker);
      }
      if (path.includes("interval=1m")) {
        return Promise.resolve(intraday);
      }
      if (path.includes("interval=1d")) {
        return Promise.resolve(quote);
      }
      return Promise.reject(new Error(`unexpected ${path}`));
    });

    render(
      <MemoryRouter initialEntries={["/market"]}>
        <AppRoutes />
      </MemoryRouter>,
    );

    expect(await screen.findByText("$75,805.98")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "ETH-USD" }));

    expect(await screen.findByText("1-minute candles are unavailable. No price was invented.")).toBeInTheDocument();
    expect(screen.queryByRole("img", { name: /ETH-USD 1-minute candlestick chart/i })).not.toBeInTheDocument();
    expect(ethMinuteCalls).toBe(2);
  });
});

const ethMinute: BarsResponse = {
  ...intraday,
  symbol: "ETH-USD",
  last_close: "2231.49",
  retrieved_at: "2026-11-08T04:49:35Z",
  disclaimer:
    "ETH-USD 1-minute candles from Coinbase. Not a consolidated quote. Not investment advice. No order is sent.",
  bars: [
    {
      bar_start: "2026-11-08T04:49:00Z",
      open: "2231.49",
      high: "2231.49",
      low: "2231.49",
      close: "2231.49",
      volume: "1",
    },
  ],
};

const ethDailyPrint: BarsResponse = {
  ...quote,
  symbol: "ETH-USD",
  last_close: "2231.82",
  bars: [{ ...quote.bars[0], close: "2231.82" }],
};

const ethTickerPrint: TickerResponse = {
  ...ticker,
  symbol: "ETH-USD",
  price: "2230.10",
  bid: "2230.10",
  ask: "2230.11",
};

describe("market print age", () => {
  beforeEach(() => {
    vi.mocked(apiGet).mockReset();
    vi.spyOn(Date, "now").mockReturnValue(Date.parse("2026-11-08T05:40:00.000Z"));
  });

  afterEach(() => {
    vi.mocked(Date.now).mockRestore();
  });

  it("keeps a 21-second-old last trade and says the print is stale", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.includes("/ticker")) {
        return Promise.resolve({
          ...ticker,
          trade_time: "2026-11-08T05:39:39.000000000Z",
        });
      }
      return Promise.reject(new Error("down"));
    });

    render(
      <MemoryRouter initialEntries={["/market"]}>
        <AppRoutes />
      </MemoryRouter>,
    );

    expect((await screen.findAllByText("$75,764.49")).length).toBeGreaterThan(0);
    expect(screen.getByText("Exchange time 2026-11-08T05:39:39.000000000Z")).toBeInTheDocument();
    expect(screen.getByText("Print is stale. Age 21 seconds.")).toBeInTheDocument();
  });
});

describe("market bid-ask spread", () => {
  beforeEach(() => {
    vi.useRealTimers();
    vi.mocked(apiGet).mockReset();
  });

  it("keeps the last trade and shows the spread in USD and basis points", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.includes("/ticker")) {
        return Promise.resolve({ ...ticker, price: "100.05", bid: "100.00", ask: "100.10" });
      }
      return Promise.reject(new Error("down"));
    });

    render(
      <MemoryRouter initialEntries={["/market"]}>
        <AppRoutes />
      </MemoryRouter>,
    );

    expect(await screen.findByText("$100.05")).toBeInTheDocument();
    expect(screen.getByText("Spread $0.10 (10.00 bp).")).toBeInTheDocument();
  });

  it("keeps the last trade and does not invent a spread when the ask is missing", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.includes("/ticker")) {
        return Promise.resolve({ ...ticker, ask: "" });
      }
      return Promise.reject(new Error("down"));
    });

    render(
      <MemoryRouter initialEntries={["/market"]}>
        <AppRoutes />
      </MemoryRouter>,
    );

    expect((await screen.findAllByText("$75,764.49")).length).toBeGreaterThan(0);
    expect(screen.getByText("Spread is unavailable.")).toBeInTheDocument();
    expect(screen.queryByText(/Spread \$/)).not.toBeInTheDocument();
  });
});

describe("market base volume and last size", () => {
  beforeEach(() => {
    vi.useRealTimers();
    vi.mocked(apiGet).mockReset();
  });

  it("shows the 24-hour base volume and last trade size with the price", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.includes("/ticker")) {
        return Promise.resolve(ticker);
      }
      return Promise.reject(new Error("down"));
    });

    render(
      <MemoryRouter initialEntries={["/market"]}>
        <AppRoutes />
      </MemoryRouter>,
    );

    expect((await screen.findAllByText("$75,764.49")).length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "24-hour base volume" })).toBeInTheDocument();
    expect(screen.getByText("2,022.50285353")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Last trade size" })).toBeInTheDocument();
    expect(screen.getByText("0.00000011")).toBeInTheDocument();
    expect(screen.getAllByText("BTC").length).toBeGreaterThan(0);
    expect(screen.queryByText("$2,022.50285353")).not.toBeInTheDocument();
  });

  it("says volume is unavailable and does not invent a number", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.includes("/ticker")) {
        return Promise.resolve({ ...ticker, volume: "" });
      }
      return Promise.reject(new Error("down"));
    });

    render(
      <MemoryRouter initialEntries={["/market"]}>
        <AppRoutes />
      </MemoryRouter>,
    );

    expect((await screen.findAllByText("$75,764.49")).length).toBeGreaterThan(0);
    expect(screen.getByText("Volume is unavailable.")).toBeInTheDocument();
    expect(screen.getByText("0.00000011")).toBeInTheDocument();
    expect(screen.queryByText("2,022.50285353")).not.toBeInTheDocument();
    expect(screen.queryByText("2022.50285353")).not.toBeInTheDocument();
  });
});

describe("market day position", () => {
  beforeEach(() => {
    vi.useRealTimers();
    vi.mocked(apiGet).mockReset();
  });

  it("shows a mid-range print from the daily bar already on the page", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.includes("/ticker")) {
        return Promise.resolve({ ...ticker, price: "150.00", bid: "150.00", ask: "150.01" });
      }
      if (path.includes("interval=1d")) {
        return Promise.resolve({
          ...quote,
          bars: [{ ...quote.bars[0], high: "200.00", low: "100.00", close: "150.00" }],
        });
      }
      return Promise.reject(new Error("down"));
    });

    render(
      <MemoryRouter initialEntries={["/market"]}>
        <AppRoutes />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Position in the day 50.00%.")).toBeInTheDocument();
    expect(screen.getAllByText("$150.00").length).toBeGreaterThan(0);
    expect(screen.getByText("High $200.00")).toBeInTheDocument();
    expect(screen.getByText("Low $100.00")).toBeInTheDocument();
  });

  it("shows a print above the high without changing that high or low", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.includes("/ticker")) {
        return Promise.resolve({ ...ticker, price: "120.00", bid: "119.99", ask: "120.00" });
      }
      if (path.includes("interval=1d")) {
        return Promise.resolve({
          ...quote,
          bars: [{ ...quote.bars[0], high: "110.00", low: "100.00", close: "110.00" }],
        });
      }
      return Promise.reject(new Error("down"));
    });

    render(
      <MemoryRouter initialEntries={["/market"]}>
        <AppRoutes />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Position in the day 200.00%. Print is outside the daily candle.")).toBeInTheDocument();
    expect(screen.getAllByText("$120.00").length).toBeGreaterThan(0);
    expect(screen.getByText("High $110.00")).toBeInTheDocument();
    expect(screen.getByText("Low $100.00")).toBeInTheDocument();
    expect(screen.queryByText("High $120.00")).not.toBeInTheDocument();
  });

  it("says the position is unavailable for a flat daily range", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.includes("/ticker")) {
        return Promise.resolve({ ...ticker, price: "40.00", bid: "40.00", ask: "40.00" });
      }
      if (path.includes("interval=1d")) {
        return Promise.resolve({
          ...quote,
          bars: [{ ...quote.bars[0], high: "40.00", low: "40.00", close: "40.00" }],
        });
      }
      return Promise.reject(new Error("down"));
    });

    render(
      <MemoryRouter initialEntries={["/market"]}>
        <AppRoutes />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Position in the day is unavailable.")).toBeInTheDocument();
    expect(screen.getAllByText("$40.00").length).toBeGreaterThan(0);
    expect(screen.queryByText(/Position in the day \d/)).not.toBeInTheDocument();
  });
});

const CANDLE_NOW = Date.parse("2026-11-08T05:00:00.000Z");

function agedMinute(start: string, close = "100.00"): BarsResponse {
  return {
    ...intraday,
    last_close: close,
    retrieved_at: "2026-11-08T05:00:00Z",
    bars: [
      {
        bar_start: start,
        open: close,
        high: close,
        low: close,
        close,
        volume: "1",
      },
    ],
  };
}

describe("market candle age", () => {
  beforeEach(() => {
    vi.useRealTimers();
    vi.mocked(apiGet).mockReset();
    vi.spyOn(Date, "now").mockReturnValue(CANDLE_NOW);
  });

  afterEach(() => {
    vi.mocked(Date.now).mockRestore();
  });

  function renderMinute(start: string) {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.includes("interval=1m")) {
        return Promise.resolve(agedMinute(start));
      }
      return Promise.reject(new Error("down"));
    });
    render(
      <MemoryRouter initialEntries={["/market"]}>
        <AppRoutes />
      </MemoryRouter>,
    );
  }

  it("calls a bucket that started 30 seconds ago current and not stale", async () => {
    renderMinute("2026-11-08T04:59:30Z");

    expect(await screen.findByText("$100.00")).toBeInTheDocument();
    expect(screen.getByText("Bar start (UTC) 2026-11-08T04:59:30Z.")).toBeInTheDocument();
    expect(screen.getByText("Current 1-minute candle. 30 seconds left.")).toBeInTheDocument();
    expect(screen.queryByText(/candle is stale/)).not.toBeInTheDocument();
  });

  it("does not call a candle that closed 10 seconds ago stale", async () => {
    renderMinute("2026-11-08T04:58:50Z");

    expect(await screen.findByText("$100.00")).toBeInTheDocument();
    expect(screen.getByText("Last 1-minute candle closed 10 seconds ago.")).toBeInTheDocument();
    expect(screen.queryByText(/candle is stale/)).not.toBeInTheDocument();
  });

  it("keeps the close when the candle closed 91 seconds ago", async () => {
    renderMinute("2026-11-08T04:57:29Z");

    expect(await screen.findByText("$100.00")).toBeInTheDocument();
    expect(screen.getByText("1-minute candle is stale. Age 91 seconds.")).toBeInTheDocument();
    expect(screen.queryByText("Current 1-minute candle. 30 seconds left.")).not.toBeInTheDocument();
  });

  it("does not call an unreadable candle time current", async () => {
    renderMinute("2026-11-08Tnot-readableZ");

    expect(await screen.findByText("$100.00")).toBeInTheDocument();
    expect(screen.getByText("Candle time is unreadable.")).toBeInTheDocument();
    expect(screen.queryByText(/Current 1-minute candle/)).not.toBeInTheDocument();
  });
});

describe("market print minus candle", () => {
  beforeEach(() => {
    vi.useRealTimers();
    vi.mocked(apiGet).mockReset();
  });

  function renderGap(price: string, close: string | null) {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.includes("/ticker")) {
        return Promise.resolve({ ...ticker, price, bid: price, ask: price });
      }
      if (path.includes("interval=1m") && close !== null) {
        return Promise.resolve({
          ...intraday,
          last_close: close,
          bars: [{ ...intraday.bars[1], open: close, high: close, low: close, close }],
        });
      }
      return Promise.reject(new Error("down"));
    });
    render(
      <MemoryRouter initialEntries={["/market"]}>
        <AppRoutes />
      </MemoryRouter>,
    );
  }

  it("shows the print above the 1-minute close", async () => {
    renderGap("110.00", "100.00");

    expect(await screen.findByText("Print minus candle +$10.00 (+10.00%).")).toBeInTheDocument();
    expect(screen.getAllByText("$110.00").length).toBeGreaterThan(0);
    expect(screen.getByText("$100.00")).toBeInTheDocument();
  });

  it("shows a zero gap when the print equals the close", async () => {
    renderGap("100.00", "100.00");

    expect(await screen.findByText("Print minus candle $0.00 (0.00%).")).toBeInTheDocument();
    expect(screen.getAllByText("$100.00").length).toBeGreaterThan(0);
  });

  it("shows the print below the 1-minute close", async () => {
    renderGap("90.00", "100.00");

    expect(await screen.findByText("Print minus candle -$10.00 (-10.00%).")).toBeInTheDocument();
    expect(screen.getAllByText("$90.00").length).toBeGreaterThan(0);
    expect(screen.getByText("$100.00")).toBeInTheDocument();
  });

  it("does not invent a close when the candle is missing", async () => {
    renderGap("110.00", null);

    expect((await screen.findAllByText("$110.00")).length).toBeGreaterThan(0);
    expect(screen.getByText("Print minus candle is unavailable.")).toBeInTheDocument();
    expect(screen.getByText("1-minute candles are unavailable. No price was invented.")).toBeInTheDocument();
    expect(screen.queryByText("$100.00")).not.toBeInTheDocument();
    expect(screen.queryByText(/Print minus candle \$/)).not.toBeInTheDocument();
  });
});
