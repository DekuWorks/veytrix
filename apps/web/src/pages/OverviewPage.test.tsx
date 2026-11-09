import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiGet } from "../api/client";
import type {
  BarResponse,
  BarsResponse,
  CoinbaseProduct,
  DiagnosticsResponse,
  PaperPositionResponse,
  TickerResponse,
} from "../api/types";
import { AppRoutes } from "../App";

vi.mock("../api/client", () => ({
  apiGet: vi.fn(),
}));

const diagnostics: DiagnosticsResponse = {
  service: "veytrix-api",
  env: "local",
  trading_mode: "paper",
  live_broker: "disabled",
  auth: "not_configured",
  sample_data: true,
  execution_permitted: false,
  daily_weekly_stops_enforced: false,
  rate_limit: "process_local",
  csrf: "not_implemented",
  versions: { api: "0.1.0", python: "3.14" },
};

const btc: TickerResponse = {
  symbol: "BTC-USD",
  venue: "COINBASE",
  source_id: "coinbase-exchange",
  synthetic: false,
  price: "75818.84",
  bid: "75818.84",
  ask: "75818.85",
  size: "0.01",
  volume: "1959.85",
  trade_time: "2026-11-08T04:17:13.995893464Z",
  trade_id: 1,
  retrieved_at: "2026-11-08T04:17:14Z",
  disclaimer: "Live BTC-USD last trade. Not investment advice. No order is sent.",
};

const eth: TickerResponse = {
  ...btc,
  symbol: "ETH-USD",
  price: "2234.56",
  bid: "2234.55",
  ask: "2234.56",
  volume: "37489.95",
  trade_time: "2026-11-08T04:17:21.906738619Z",
  trade_id: 2,
  disclaimer: "Live ETH-USD last trade. Not investment advice. No order is sent.",
};

const sol: TickerResponse = {
  ...btc,
  symbol: "SOL-USD",
  price: "186.42",
  bid: "186.41",
  ask: "186.43",
  volume: "88000.10",
  trade_time: "2026-11-08T05:19:40.000000Z",
  trade_id: 3,
  disclaimer: "Live SOL-USD last trade. Not investment advice. No order is sent.",
};

function daily(
  symbol: CoinbaseProduct,
  change: string,
  changePercent: string,
): BarsResponse {
  return {
    symbol,
    venue: "COINBASE",
    asset_type: "crypto",
    currency: "USD",
    source_id: "coinbase-exchange",
    interval: "1d",
    seed: null,
    synthetic: false,
    calendar_note: "Coinbase daily buckets start at 00:00 UTC.",
    disclaimer: `${symbol} daily candles from Coinbase. Not a consolidated quote. No order is sent.`,
    last_close: "999.00",
    previous_close: "1.00",
    change,
    change_percent: changePercent,
    retrieved_at: "2026-11-08T05:24:00Z",
    source_url: `https://api.exchange.coinbase.com/products/${symbol}/candles`,
    bars: [],
  };
}

function card(name: string): HTMLElement {
  const heading = screen.getByRole("heading", { name });
  const article = heading.closest("article");
  if (article === null) {
    throw new Error(`No card for ${name}`);
  }
  return article;
}

function renderOverview() {
  render(
    <MemoryRouter initialEntries={["/"]}>
      <AppRoutes />
    </MemoryRouter>,
  );
}

describe("overview prints", () => {
  beforeEach(() => {
    vi.mocked(apiGet).mockReset();
  });

  it("shows live bid and ask for BTC-USD and ETH-USD", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.endsWith("/health")) {
        return Promise.resolve({ status: "ok" });
      }
      if (path.endsWith("/ready")) {
        return Promise.resolve({ status: "ready", database: "up" });
      }
      if (path.endsWith("/diagnostics")) {
        return Promise.resolve(diagnostics);
      }
      if (path.includes("/BTC-USD/ticker")) {
        return Promise.resolve(btc);
      }
      if (path.includes("/ETH-USD/ticker")) {
        return Promise.resolve(eth);
      }
      if (path.includes("/SOL-USD/ticker")) {
        return Promise.resolve(sol);
      }
      return Promise.reject(new Error(`unexpected ${path}`));
    });

    renderOverview();

    expect(await screen.findByRole("heading", { name: "BTC-USD last trade" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "ETH-USD last trade" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "SOL-USD last trade" })).toBeInTheDocument();
    expect(screen.getAllByText("$75,818.84").length).toBeGreaterThan(0);
    expect(screen.getByText(/Bid \$75,818\.84 · ask \$75,818\.85/)).toBeInTheDocument();
    expect(screen.getByText(/Exchange time 2026-11-08T04:17:13\.995893464Z/)).toBeInTheDocument();
    expect(screen.getByText("$2,234.56")).toBeInTheDocument();
    expect(screen.getByText("$186.42")).toBeInTheDocument();
    expect(screen.getByText(/Bid \$2,234\.55 · ask \$2,234\.56/)).toBeInTheDocument();
    expect(screen.getByText(/Bid \$186\.41 · ask \$186\.43/)).toBeInTheDocument();
    expect(screen.getByText(/Exchange time 2026-11-08T04:17:21\.906738619Z/)).toBeInTheDocument();
    expect(screen.getAllByText(/No order is sent/).length).toBeGreaterThan(0);
    expect(screen.getByText("Not sent")).toBeInTheDocument();
  });

  it("marks only the failed product unavailable", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.endsWith("/health")) {
        return Promise.resolve({ status: "ok" });
      }
      if (path.endsWith("/ready")) {
        return Promise.resolve({ status: "ready", database: "down" });
      }
      if (path.endsWith("/diagnostics")) {
        return Promise.resolve(diagnostics);
      }
      if (path.includes("/BTC-USD/ticker")) {
        return Promise.resolve(btc);
      }
      if (path.includes("/ETH-USD/ticker")) {
        return Promise.reject(new Error("down"));
      }
      if (path.includes("/SOL-USD/ticker")) {
        return Promise.resolve(sol);
      }
      if (path.includes("/bars?interval=1d")) {
        return Promise.resolve(daily("ETH-USD", "-2.00", "-0.20"));
      }
      return Promise.reject(new Error(`unexpected ${path}`));
    });

    renderOverview();

    expect(await screen.findByText("$75,818.84")).toBeInTheDocument();
    expect(await screen.findByText("$186.42")).toBeInTheDocument();
    expect(await screen.findByText("Unavailable")).toBeInTheDocument();
    expect(screen.queryByText("$2,234.56")).not.toBeInTheDocument();
    expect(screen.queryByText("2234.55")).not.toBeInTheDocument();
    expect(screen.getAllByText("No price was invented.").length).toBe(1);
  });

  it("shows the API daily change on the BTC card without replacing the live print", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.endsWith("/health")) {
        return Promise.resolve({ status: "ok" });
      }
      if (path.endsWith("/ready")) {
        return Promise.resolve({ status: "ready", database: "up" });
      }
      if (path.endsWith("/diagnostics")) {
        return Promise.resolve(diagnostics);
      }
      if (path.includes("/BTC-USD/ticker")) {
        return Promise.resolve(btc);
      }
      if (path.includes("/ETH-USD/ticker")) {
        return Promise.resolve(eth);
      }
      if (path.includes("/SOL-USD/ticker")) {
        return Promise.resolve(sol);
      }
      if (path.includes("/BTC-USD/bars?interval=1d&limit=2")) {
        return Promise.resolve(daily("BTC-USD", "+5.18", "+0.01"));
      }
      if (path.includes("/ETH-USD/bars?interval=1d&limit=2")) {
        return Promise.resolve(daily("ETH-USD", "-12.40", "-0.55"));
      }
      if (path.includes("/SOL-USD/bars?interval=1d&limit=2")) {
        return Promise.resolve(daily("SOL-USD", "+0.80", "+0.43"));
      }
      return Promise.reject(new Error(`unexpected ${path}`));
    });

    renderOverview();

    const btcCard = card("BTC-USD last trade");
    expect(await screen.findByText("+$5.18 (+0.01%) versus the previous daily close.")).toBeInTheDocument();
    expect(btcCard).toHaveTextContent("$75,818.84");
    expect(btcCard).toHaveTextContent("Bid $75,818.84 · ask $75,818.85");
    expect(btcCard).toHaveTextContent("Exchange time 2026-11-08T04:17:13.995893464Z");
    expect(btcCard).toHaveTextContent("+$5.18 (+0.01%) versus the previous daily close.");
    expect(btcCard).not.toHaveTextContent("$998.00");
    expect(screen.getByText("-$12.40 (-0.55%) versus the previous daily close.")).toBeInTheDocument();
    expect(screen.getByText("+$0.80 (+0.43%) versus the previous daily close.")).toBeInTheDocument();
    expect(vi.mocked(apiGet)).not.toHaveBeenCalledWith("/api/v1/risk/size");
  });

  it("keeps the live print when that product's daily change is rejected", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.endsWith("/health")) {
        return Promise.resolve({ status: "ok" });
      }
      if (path.endsWith("/ready")) {
        return Promise.resolve({ status: "ready", database: "up" });
      }
      if (path.endsWith("/diagnostics")) {
        return Promise.resolve(diagnostics);
      }
      if (path.includes("/BTC-USD/ticker")) {
        return Promise.resolve(btc);
      }
      if (path.includes("/ETH-USD/ticker")) {
        return Promise.resolve(eth);
      }
      if (path.includes("/SOL-USD/ticker")) {
        return Promise.resolve(sol);
      }
      if (path.includes("/BTC-USD/bars")) {
        return Promise.reject(new Error("down"));
      }
      if (path.includes("/ETH-USD/bars?interval=1d&limit=2")) {
        return Promise.resolve(daily("ETH-USD", "-12.40", "-0.55"));
      }
      if (path.includes("/SOL-USD/bars?interval=1d&limit=2")) {
        return Promise.resolve(daily("SOL-USD", "+0.80", "+0.43"));
      }
      return Promise.reject(new Error(`unexpected ${path}`));
    });

    renderOverview();

    expect(
      await screen.findByText("Daily change versus the previous daily close is unavailable."),
    ).toBeInTheDocument();
    const btcCard = card("BTC-USD last trade");
    expect(btcCard).toHaveTextContent("$75,818.84");
    expect(btcCard).toHaveTextContent("Bid $75,818.84 · ask $75,818.85");
    expect(btcCard).toHaveTextContent("Exchange time 2026-11-08T04:17:13.995893464Z");
    expect(btcCard).toHaveTextContent("Daily change versus the previous daily close is unavailable.");
    expect(btcCard).not.toHaveTextContent("+$5.18");
    expect(screen.getByText("$2,234.56")).toBeInTheDocument();
    expect(screen.getByText("$186.42")).toBeInTheDocument();
    expect(screen.getByText("-$12.40 (-0.55%) versus the previous daily close.")).toBeInTheDocument();
    expect(screen.queryByText("No price was invented.")).not.toBeInTheDocument();
  });

  it("shows a normal spread, a locked book, and no invented spread for a crossed book", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.endsWith("/health")) {
        return Promise.resolve({ status: "ok" });
      }
      if (path.endsWith("/ready")) {
        return Promise.resolve({ status: "ready", database: "up" });
      }
      if (path.endsWith("/diagnostics")) {
        return Promise.resolve(diagnostics);
      }
      if (path === "/api/v1/portfolio/positions") {
        return Promise.resolve({ positions: [] });
      }
      if (path.includes("/BTC-USD/ticker")) {
        return Promise.resolve({ ...btc, price: "100.05", bid: "100.00", ask: "100.10" });
      }
      if (path.includes("/ETH-USD/ticker")) {
        return Promise.resolve({ ...eth, price: "50.00", bid: "50.00", ask: "50.00" });
      }
      if (path.includes("/SOL-USD/ticker")) {
        return Promise.resolve({ ...sol, price: "10.00", bid: "10.00", ask: "9.50" });
      }
      if (path.includes("/bars?interval=1d")) {
        return Promise.resolve(daily("BTC-USD", "+5.18", "+0.01"));
      }
      return Promise.reject(new Error(`unexpected ${path}`));
    });

    renderOverview();

    const btcCard = card("BTC-USD last trade");
    expect(await screen.findByText("$100.05")).toBeInTheDocument();
    expect(btcCard).toHaveTextContent("$100.05");
    expect(btcCard).toHaveTextContent("Spread $0.10 (10.00 bp).");
    expect(btcCard).toHaveTextContent(
      "Bid-ask spread from the Coinbase print. Not a consolidated quote. No order is sent.",
    );
    const ethCard = card("ETH-USD last trade");
    expect(ethCard).toHaveTextContent("$50.00");
    expect(ethCard).toHaveTextContent("Spread $0.00 (0.00 bp).");
    const solCard = card("SOL-USD last trade");
    expect(solCard).toHaveTextContent("$10.00");
    expect(solCard).toHaveTextContent("Spread is unavailable.");
    expect(solCard).not.toHaveTextContent("Spread $0.50");
    expect(solCard).not.toHaveTextContent("Spread $-0.50");
  });

  it("shows the in-progress day high, low, and range without replacing the last trade", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.endsWith("/health")) {
        return Promise.resolve({ status: "ok" });
      }
      if (path.endsWith("/ready")) {
        return Promise.resolve({ status: "ready", database: "up" });
      }
      if (path.endsWith("/diagnostics")) {
        return Promise.resolve(diagnostics);
      }
      if (path === "/api/v1/portfolio/positions") {
        return Promise.resolve({ positions: [] });
      }
      if (path.includes("/BTC-USD/ticker")) {
        return Promise.resolve(btc);
      }
      if (path.includes("/ETH-USD/ticker")) {
        return Promise.resolve(eth);
      }
      if (path.includes("/SOL-USD/ticker")) {
        return Promise.resolve(sol);
      }
      if (path.includes("/BTC-USD/bars")) {
        return Promise.resolve({
          ...daily("BTC-USD", "+5.18", "+0.01"),
          bars: [
            candle("2026-11-07T00:00:00Z", "1.00", "0.50"),
            candle("2026-11-08T00:00:00Z", "110.50", "100.25"),
          ],
        });
      }
      if (path.includes("/ETH-USD/bars")) {
        return Promise.resolve({
          ...daily("ETH-USD", "-12.40", "-0.55"),
          bars: [candle("2026-11-08T00:00:00Z", "40.00", "40.00")],
        });
      }
      if (path.includes("/SOL-USD/bars")) {
        return Promise.resolve({
          ...daily("SOL-USD", "+0.80", "+0.43"),
          bars: [candle("2026-11-08T00:00:00Z", "9.00", "10.00")],
        });
      }
      return Promise.reject(new Error(`unexpected ${path}`));
    });

    renderOverview();

    const btcCard = card("BTC-USD last trade");
    expect(await screen.findByText("$75,818.84")).toBeInTheDocument();
    expect(btcCard).toHaveTextContent("$75,818.84");
    expect(btcCard).toHaveTextContent("Spread $0.01 (0.00 bp).");
    expect(btcCard).toHaveTextContent("+$5.18 (+0.01%) versus the previous daily close.");
    expect(btcCard).toHaveTextContent("Day high $110.50. Day low $100.25. Day range $10.25.");
    expect(btcCard).not.toHaveTextContent("Day high $1.00");
    expect(btcCard).not.toHaveTextContent("$998.00");
    expect(btcCard).toHaveTextContent(
      "In-progress UTC day from the Coinbase daily candle. Not a settlement. No order is sent.",
    );
    const ethCard = card("ETH-USD last trade");
    expect(ethCard).toHaveTextContent("$2,234.56");
    expect(ethCard).toHaveTextContent("Day high $40.00. Day low $40.00. Day range $0.00.");
    const solCard = card("SOL-USD last trade");
    expect(solCard).toHaveTextContent("$186.42");
    expect(solCard).toHaveTextContent("Day range is unavailable.");
    expect(solCard).not.toHaveTextContent("Day range $1.00");
    expect(solCard).not.toHaveTextContent("Day high $9.00");
  });

  it("keeps another card's range when one daily fetch fails and a high is missing", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.endsWith("/health")) {
        return Promise.resolve({ status: "ok" });
      }
      if (path.endsWith("/ready")) {
        return Promise.resolve({ status: "ready", database: "up" });
      }
      if (path.endsWith("/diagnostics")) {
        return Promise.resolve(diagnostics);
      }
      if (path === "/api/v1/portfolio/positions") {
        return Promise.resolve({ positions: [] });
      }
      if (path.includes("/BTC-USD/ticker")) {
        return Promise.resolve(btc);
      }
      if (path.includes("/ETH-USD/ticker")) {
        return Promise.resolve(eth);
      }
      if (path.includes("/SOL-USD/ticker")) {
        return Promise.resolve(sol);
      }
      if (path.includes("/BTC-USD/bars")) {
        return Promise.reject(new Error("down"));
      }
      if (path.includes("/ETH-USD/bars")) {
        return Promise.resolve({
          ...daily("ETH-USD", "-12.40", "-0.55"),
          bars: [candle("2026-11-08T00:00:00Z", "40.00", "32.00")],
        });
      }
      if (path.includes("/SOL-USD/bars")) {
        return Promise.resolve({
          ...daily("SOL-USD", "+0.80", "+0.43"),
          bars: [{ ...candle("2026-11-08T00:00:00Z", "10.00", "9.00"), high: "" }],
        });
      }
      return Promise.reject(new Error(`unexpected ${path}`));
    });

    renderOverview();

    const ethCard = card("ETH-USD last trade");
    expect(await screen.findByText("Day high $40.00. Day low $32.00. Day range $8.00.")).toBeInTheDocument();
    expect(ethCard).toHaveTextContent("$2,234.56");
    expect(ethCard).toHaveTextContent("Day high $40.00. Day low $32.00. Day range $8.00.");
    const btcCard = card("BTC-USD last trade");
    expect(btcCard).toHaveTextContent("$75,818.84");
    expect(btcCard).toHaveTextContent("Spread $0.01 (0.00 bp).");
    expect(btcCard).toHaveTextContent("Day range is unavailable.");
    expect(btcCard).not.toHaveTextContent("Day range $8.00");
    const solCard = card("SOL-USD last trade");
    expect(solCard).toHaveTextContent("$186.42");
    expect(solCard).toHaveTextContent("Day range is unavailable.");
    expect(solCard).not.toHaveTextContent("Day high $10.00");
  });

  it("shows base volume and last trade size, and one missing size does not clear another card", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.endsWith("/health")) {
        return Promise.resolve({ status: "ok" });
      }
      if (path.endsWith("/ready")) {
        return Promise.resolve({ status: "ready", database: "up" });
      }
      if (path.endsWith("/diagnostics")) {
        return Promise.resolve(diagnostics);
      }
      if (path === "/api/v1/portfolio/positions") {
        return Promise.resolve({ positions: [] });
      }
      if (path.includes("/BTC-USD/ticker")) {
        return Promise.resolve(btc);
      }
      if (path.includes("/ETH-USD/ticker")) {
        return Promise.resolve({ ...eth, size: "" });
      }
      if (path.includes("/SOL-USD/ticker")) {
        return Promise.resolve({ ...sol, volume: "" });
      }
      if (path.includes("/BTC-USD/bars")) {
        return Promise.resolve({
          ...daily("BTC-USD", "+5.18", "+0.01"),
          bars: [candle("2026-11-08T00:00:00Z", "110.50", "100.25")],
        });
      }
      if (path.includes("/ETH-USD/bars")) {
        return Promise.resolve(daily("ETH-USD", "-12.40", "-0.55"));
      }
      if (path.includes("/SOL-USD/bars")) {
        return Promise.resolve({
          ...daily("SOL-USD", "+0.80", "+0.43"),
          bars: [candle("2026-11-08T00:00:00Z", "90.00", "80.00")],
        });
      }
      return Promise.reject(new Error(`unexpected ${path}`));
    });

    renderOverview();

    const btcCard = card("BTC-USD last trade");
    expect(await screen.findByText("$75,818.84")).toBeInTheDocument();
    expect(btcCard).toHaveTextContent("$75,818.84");
    expect(btcCard).toHaveTextContent("24-hour base volume 1,959.85 BTC.");
    expect(btcCard).toHaveTextContent("Last trade size 0.01 BTC.");
    expect(btcCard).toHaveTextContent("Spread $0.01 (0.00 bp).");
    expect(btcCard).toHaveTextContent("Day high $110.50. Day low $100.25. Day range $10.25.");
    expect(btcCard).toHaveTextContent(
      "From the Coinbase ticker. Base currency, not USD. Not a consolidated quote. No order is sent.",
    );
    const ethCard = card("ETH-USD last trade");
    expect(ethCard).toHaveTextContent("$2,234.56");
    expect(ethCard).toHaveTextContent("24-hour base volume 37,489.95 ETH.");
    expect(ethCard).toHaveTextContent("Last size is unavailable.");
    expect(ethCard).not.toHaveTextContent("Last trade size");
    const solCard = card("SOL-USD last trade");
    expect(solCard).toHaveTextContent("$186.42");
    expect(solCard).toHaveTextContent("Volume is unavailable.");
    expect(solCard).toHaveTextContent("Last trade size 0.01 SOL.");
    expect(solCard).toHaveTextContent("Day high $90.00. Day low $80.00. Day range $10.00.");
    expect(solCard).not.toHaveTextContent("88,000");
    expect(solCard).not.toHaveTextContent("88000");
  });

  it("shows the last trade's share of the in-progress day range", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.endsWith("/health")) {
        return Promise.resolve({ status: "ok" });
      }
      if (path.endsWith("/ready")) {
        return Promise.resolve({ status: "ready", database: "up" });
      }
      if (path.endsWith("/diagnostics")) {
        return Promise.resolve(diagnostics);
      }
      if (path === "/api/v1/portfolio/positions") {
        return Promise.resolve({ positions: [] });
      }
      if (path.includes("/BTC-USD/ticker")) {
        return Promise.resolve({ ...btc, price: "100.00", bid: "100.00", ask: "100.01" });
      }
      if (path.includes("/ETH-USD/ticker")) {
        return Promise.resolve({ ...eth, price: "200.00", bid: "200.00", ask: "200.01" });
      }
      if (path.includes("/SOL-USD/ticker")) {
        return Promise.resolve({ ...sol, price: "150.00", bid: "150.00", ask: "150.01" });
      }
      if (path.includes("/BTC-USD/bars")) {
        return Promise.resolve({
          ...daily("BTC-USD", "+5.18", "+0.01"),
          bars: [
            candle("2026-11-07T00:00:00Z", "1.00", "0.00"),
            candle("2026-11-08T00:00:00Z", "110.00", "100.00"),
          ],
        });
      }
      if (path.includes("/ETH-USD/bars")) {
        return Promise.resolve({
          ...daily("ETH-USD", "-12.40", "-0.55"),
          bars: [candle("2026-11-08T00:00:00Z", "200.00", "100.00")],
        });
      }
      if (path.includes("/SOL-USD/bars")) {
        return Promise.resolve({
          ...daily("SOL-USD", "+0.80", "+0.43"),
          bars: [candle("2026-11-08T00:00:00Z", "200.00", "100.00")],
        });
      }
      return Promise.reject(new Error(`unexpected ${path}`));
    });

    renderOverview();

    const btcCard = card("BTC-USD last trade");
    expect(await screen.findByText("Position in the day 0.00%.")).toBeInTheDocument();
    expect(btcCard).toHaveTextContent("$100.00");
    expect(btcCard).toHaveTextContent("24-hour base volume 1,959.85 BTC.");
    expect(btcCard).toHaveTextContent("Last trade size 0.01 BTC.");
    expect(btcCard).toHaveTextContent("Day high $110.00. Day low $100.00. Day range $10.00.");
    expect(btcCard).toHaveTextContent("Position in the day 0.00%.");
    expect(btcCard).not.toHaveTextContent("Print is outside the daily candle.");
    expect(btcCard).not.toHaveTextContent("Day high $1.00");
    expect(btcCard).toHaveTextContent(
      "Share of the in-progress UTC day range, from the low. Not a trading signal. Not a settlement. No order is sent.",
    );
    const ethCard = card("ETH-USD last trade");
    expect(ethCard).toHaveTextContent("$200.00");
    expect(ethCard).toHaveTextContent("Position in the day 100.00%.");
    expect(ethCard).toHaveTextContent("Day high $200.00. Day low $100.00. Day range $100.00.");
    const solCard = card("SOL-USD last trade");
    expect(solCard).toHaveTextContent("$150.00");
    expect(solCard).toHaveTextContent("Position in the day 50.00%.");
    expect(solCard).toHaveTextContent("Spread $0.01 (0.67 bp).");
  });

  it("keeps an outside print and does not invent a percent for a flat range or a missing low", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.endsWith("/health")) {
        return Promise.resolve({ status: "ok" });
      }
      if (path.endsWith("/ready")) {
        return Promise.resolve({ status: "ready", database: "up" });
      }
      if (path.endsWith("/diagnostics")) {
        return Promise.resolve(diagnostics);
      }
      if (path === "/api/v1/portfolio/positions") {
        return Promise.resolve({ positions: [] });
      }
      if (path.includes("/BTC-USD/ticker")) {
        return Promise.resolve({ ...btc, price: "120.00", bid: "119.99", ask: "120.00" });
      }
      if (path.includes("/ETH-USD/ticker")) {
        return Promise.resolve({ ...eth, price: "40.00", bid: "40.00", ask: "40.00" });
      }
      if (path.includes("/SOL-USD/ticker")) {
        return Promise.resolve({ ...sol, price: "10.00", bid: "10.00", ask: "10.01" });
      }
      if (path.includes("/BTC-USD/bars")) {
        return Promise.resolve({
          ...daily("BTC-USD", "+5.18", "+0.01"),
          bars: [candle("2026-11-08T00:00:00Z", "110.00", "100.00")],
        });
      }
      if (path.includes("/ETH-USD/bars")) {
        return Promise.resolve({
          ...daily("ETH-USD", "-12.40", "-0.55"),
          bars: [candle("2026-11-08T00:00:00Z", "40.00", "40.00")],
        });
      }
      if (path.includes("/SOL-USD/bars")) {
        return Promise.resolve({
          ...daily("SOL-USD", "+0.80", "+0.43"),
          bars: [{ ...candle("2026-11-08T00:00:00Z", "12.00", "9.00"), low: "" }],
        });
      }
      return Promise.reject(new Error(`unexpected ${path}`));
    });

    renderOverview();

    const btcCard = card("BTC-USD last trade");
    expect(await screen.findByText("Position in the day 200.00%. Print is outside the daily candle.")).toBeInTheDocument();
    expect(btcCard).toHaveTextContent("$120.00");
    expect(btcCard).toHaveTextContent("Day high $110.00. Day low $100.00. Day range $10.00.");
    expect(btcCard).not.toHaveTextContent("Day high $120.00");
    const ethCard = card("ETH-USD last trade");
    expect(ethCard).toHaveTextContent("$40.00");
    expect(ethCard).toHaveTextContent("Day high $40.00. Day low $40.00. Day range $0.00.");
    expect(ethCard).toHaveTextContent("Position in the day is unavailable.");
    expect(ethCard).not.toHaveTextContent("Position in the day 0.00%");
    const solCard = card("SOL-USD last trade");
    expect(solCard).toHaveTextContent("$10.00");
    expect(solCard).toHaveTextContent("Last trade size 0.01 SOL.");
    expect(solCard).toHaveTextContent("Day range is unavailable.");
    expect(solCard).toHaveTextContent("Position in the day is unavailable.");
    expect(solCard).not.toHaveTextContent("Position in the day 1");
  });

  it("keeps another card's day position when one daily fetch fails", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.endsWith("/health")) {
        return Promise.resolve({ status: "ok" });
      }
      if (path.endsWith("/ready")) {
        return Promise.resolve({ status: "ready", database: "up" });
      }
      if (path.endsWith("/diagnostics")) {
        return Promise.resolve(diagnostics);
      }
      if (path === "/api/v1/portfolio/positions") {
        return Promise.resolve({ positions: [] });
      }
      if (path.includes("/BTC-USD/ticker")) {
        return Promise.resolve(btc);
      }
      if (path.includes("/ETH-USD/ticker")) {
        return Promise.resolve({ ...eth, price: "150.00", bid: "150.00", ask: "150.01" });
      }
      if (path.includes("/SOL-USD/ticker")) {
        return Promise.resolve({ ...sol, price: "125.00", bid: "125.00", ask: "125.01" });
      }
      if (path.includes("/BTC-USD/bars")) {
        return Promise.reject(new Error("down"));
      }
      if (path.includes("/ETH-USD/bars")) {
        return Promise.resolve({
          ...daily("ETH-USD", "-12.40", "-0.55"),
          bars: [candle("2026-11-08T00:00:00Z", "200.00", "100.00")],
        });
      }
      if (path.includes("/SOL-USD/bars")) {
        return Promise.resolve({
          ...daily("SOL-USD", "+0.80", "+0.43"),
          bars: [candle("2026-11-08T00:00:00Z", "200.00", "100.00")],
        });
      }
      return Promise.reject(new Error(`unexpected ${path}`));
    });

    renderOverview();

    const ethCard = card("ETH-USD last trade");
    expect(await screen.findByText("Position in the day 50.00%.")).toBeInTheDocument();
    expect(ethCard).toHaveTextContent("$150.00");
    expect(ethCard).toHaveTextContent("Day high $200.00. Day low $100.00. Day range $100.00.");
    const solCard = card("SOL-USD last trade");
    expect(solCard).toHaveTextContent("$125.00");
    expect(solCard).toHaveTextContent("Position in the day 25.00%.");
    const btcCard = card("BTC-USD last trade");
    expect(btcCard).toHaveTextContent("$75,818.84");
    expect(btcCard).toHaveTextContent("Spread $0.01 (0.00 bp).");
    expect(btcCard).toHaveTextContent("24-hour base volume 1,959.85 BTC.");
    expect(btcCard).toHaveTextContent("Last trade size 0.01 BTC.");
    expect(btcCard).toHaveTextContent("Day range is unavailable.");
    expect(btcCard).toHaveTextContent("Position in the day is unavailable.");
    expect(btcCard).not.toHaveTextContent("Position in the day 50.00%");
    expect(btcCard).not.toHaveTextContent("Position in the day 25.00%");
  });
});

function candle(start: string, high: string, low: string): BarResponse {
  return { bar_start: start, open: low, high, low, close: low, volume: "1" };
}

function position(
  symbol: CoinbaseProduct,
  entry: string,
  stop: string,
  shares: number,
): PaperPositionResponse {
  return {
    id: `${symbol}-${entry}`,
    symbol,
    entry,
    stop,
    shares,
    notional: "1.00",
    planned_risk: "1.00",
    binding_constraint: "allocation",
    exchange_time: "2026-11-08T05:33:43.574297Z",
    recorded_at: "2026-11-08T05:33:52.111114Z",
    execution_permitted: false,
    order_submitted: false,
  };
}

function printsAnd(extra: (path: string) => Promise<unknown> | undefined) {
  vi.mocked(apiGet).mockImplementation((path: string) => {
    const handled = extra(path);
    if (handled !== undefined) {
      return handled;
    }
    if (path.endsWith("/health")) {
      return Promise.resolve({ status: "ok" });
    }
    if (path.endsWith("/ready")) {
      return Promise.resolve({ status: "ready", database: "up" });
    }
    if (path.endsWith("/diagnostics")) {
      return Promise.resolve(diagnostics);
    }
    if (path.includes("/BTC-USD/ticker")) {
      return Promise.resolve(btc);
    }
    if (path.includes("/ETH-USD/ticker")) {
      return Promise.resolve(eth);
    }
    if (path.includes("/SOL-USD/ticker")) {
      return Promise.resolve(sol);
    }
    if (path.includes("/bars?interval=1d")) {
      return Promise.resolve(daily("BTC-USD", "+5.18", "+0.01"));
    }
    return Promise.reject(new Error(`unexpected ${path}`));
  });
}

describe("overview paper book", () => {
  beforeEach(() => {
    vi.mocked(apiGet).mockReset();
  });

  it("shows the empty sentence when no paper positions are stored", async () => {
    printsAnd((path) =>
      path === "/api/v1/portfolio/positions" ? Promise.resolve({ positions: [] }) : undefined,
    );

    renderOverview();

    expect(await screen.findByText("No paper positions recorded yet.")).toBeInTheDocument();
    expect(
      screen.getByText("Paper book on this machine. Not a fill. The stop is not enforced. No order is sent."),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Unrealised total/)).not.toBeInTheDocument();
    expect(vi.mocked(apiGet)).not.toHaveBeenCalledWith("/api/v1/risk/size");
  });

  it("shows each unrealised figure and the total from the live prints", async () => {
    const rows = [
      position("BTC-USD", "75800", "75000", 1),
      position("ETH-USD", "2230", "2200", 2),
    ];
    printsAnd((path) =>
      path === "/api/v1/portfolio/positions" ? Promise.resolve({ positions: rows }) : undefined,
    );

    renderOverview();

    const btcRow = await screen.findByRole("heading", { name: "BTC-USD" });
    const ethRow = screen.getByRole("heading", { name: "ETH-USD" });
    expect(btcRow.closest("li")).toHaveTextContent("Shares 1");
    expect(btcRow.closest("li")).toHaveTextContent("Entry 75800");
    expect(btcRow.closest("li")).toHaveTextContent("Unrealised +$18.84.");
    expect(btcRow.closest("li")).toHaveTextContent("Distance to stop +$818.84 (+1.09%).");
    expect(ethRow.closest("li")).toHaveTextContent("Shares 2");
    expect(ethRow.closest("li")).toHaveTextContent("Entry 2230");
    expect(ethRow.closest("li")).toHaveTextContent("Unrealised +$9.12.");
    expect(ethRow.closest("li")).toHaveTextContent("Distance to stop +$34.56 (+1.57%).");
    expect(screen.getByText("Unrealised total +$27.96.")).toBeInTheDocument();
    expect(vi.mocked(apiGet)).not.toHaveBeenCalledWith("/api/v1/risk/size");
  });

  it("keeps a row when its ticker is missing and marks the total incomplete", async () => {
    const rows = [
      position("BTC-USD", "75800", "75000", 1),
      position("ETH-USD", "2230", "2200", 2),
    ];
    printsAnd((path) => {
      if (path === "/api/v1/portfolio/positions") {
        return Promise.resolve({ positions: rows });
      }
      if (path.includes("/ETH-USD/ticker")) {
        return Promise.reject(new Error("down"));
      }
      return undefined;
    });

    renderOverview();

    const ethRow = await screen.findByRole("heading", { name: "ETH-USD" });
    expect(ethRow.closest("li")).toHaveTextContent("Shares 2");
    expect(ethRow.closest("li")).toHaveTextContent("Entry 2230");
    expect(ethRow.closest("li")).toHaveTextContent("Unrealised is unavailable.");
    expect(ethRow.closest("li")).toHaveTextContent("Distance to stop is unavailable.");
    expect(ethRow.closest("li")).not.toHaveTextContent("Print is stale");
    expect(ethRow.closest("li")).not.toHaveTextContent("Exchange time is unreadable.");
    expect(screen.getByText("Unrealised +$18.84.")).toBeInTheDocument();
    expect(screen.getByText("Unrealised total is incomplete.")).toBeInTheDocument();
    expect(screen.queryByText("Unrealised total +$18.84.")).not.toBeInTheDocument();
    expect(screen.queryByText("Unrealised total +$27.96.")).not.toBeInTheDocument();
  });

  it("shows the book unavailable when the positions request is rejected", async () => {
    printsAnd((path) =>
      path === "/api/v1/portfolio/positions" ? Promise.reject(new Error("down")) : undefined,
    );

    renderOverview();

    expect(await screen.findByText("The paper book is unavailable.")).toBeInTheDocument();
    expect(screen.queryByText("No paper positions recorded yet.")).not.toBeInTheDocument();
    expect(screen.queryByText("111.11")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "BTC-USD" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "ETH-USD" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "SOL-USD" })).not.toBeInTheDocument();
  });

  it("marks a 21-second-old book row stale, leaves a 5-second row quiet, and does not call an unreadable time current", async () => {
    vi.spyOn(Date, "now").mockReturnValue(Date.parse("2026-11-08T05:40:00.000Z"));
    const rows = [
      position("BTC-USD", "75800", "75000", 1),
      position("ETH-USD", "2230", "2200", 2),
      position("SOL-USD", "180", "170", 1),
    ];
    printsAnd((path) => {
      if (path === "/api/v1/portfolio/positions") {
        return Promise.resolve({ positions: rows });
      }
      if (path.includes("/BTC-USD/ticker")) {
        return Promise.resolve({ ...btc, trade_time: "2026-11-08T05:39:39.000000000Z" });
      }
      if (path.includes("/ETH-USD/ticker")) {
        return Promise.resolve({ ...eth, trade_time: "2026-11-08T05:39:55.000Z" });
      }
      if (path.includes("/SOL-USD/ticker")) {
        return Promise.resolve({ ...sol, trade_time: "2026-11-08Tnot-readableZ" });
      }
      return undefined;
    });

    renderOverview();

    const btcRow = (await screen.findByRole("heading", { name: "BTC-USD" })).closest("li");
    const ethRow = screen.getByRole("heading", { name: "ETH-USD" }).closest("li");
    const solRow = screen.getByRole("heading", { name: "SOL-USD" }).closest("li");
    expect(btcRow).toHaveTextContent("Unrealised +$18.84.");
    expect(btcRow).toHaveTextContent("Distance to stop +$818.84 (+1.09%).");
    expect(btcRow).toHaveTextContent("Print is stale. Age 21 seconds.");
    expect(ethRow).toHaveTextContent("Unrealised +$9.12.");
    expect(ethRow).toHaveTextContent("Distance to stop +$34.56 (+1.57%).");
    expect(ethRow).not.toHaveTextContent("Print is stale");
    expect(solRow).toHaveTextContent("Unrealised +$6.42.");
    expect(solRow).toHaveTextContent("Distance to stop +$16.42 (+9.66%).");
    expect(solRow).toHaveTextContent("Exchange time is unreadable.");
    expect(solRow).not.toHaveTextContent("Print is stale");
    expect(screen.getByText("Unrealised total +$34.38.")).toBeInTheDocument();
    vi.mocked(Date.now).mockRestore();
  });

  it("shows a gain, a loss, and a flat print as a percent of entry", async () => {
    const rows = [
      position("BTC-USD", "100.00", "90.00", 3),
      position("ETH-USD", "100.00", "90.00", 2),
      position("SOL-USD", "100.00", "90.00", 1),
    ];
    printsAnd((path) => {
      if (path === "/api/v1/portfolio/positions") {
        return Promise.resolve({ positions: rows });
      }
      if (path.includes("/BTC-USD/ticker")) {
        return Promise.resolve({ ...btc, price: "110.00" });
      }
      if (path.includes("/ETH-USD/ticker")) {
        return Promise.resolve({ ...eth, price: "90.00" });
      }
      if (path.includes("/SOL-USD/ticker")) {
        return Promise.resolve({ ...sol, price: "100.00" });
      }
      return undefined;
    });

    renderOverview();

    const btcRow = (await screen.findByRole("heading", { name: "BTC-USD" })).closest("li");
    const ethRow = screen.getByRole("heading", { name: "ETH-USD" }).closest("li");
    const solRow = screen.getByRole("heading", { name: "SOL-USD" }).closest("li");
    expect(btcRow).toHaveTextContent("Unrealised +$30.");
    expect(btcRow).toHaveTextContent("Unrealised percent +10.00%.");
    expect(btcRow).toHaveTextContent("Distance to stop +$20 (+22.22%).");
    expect(ethRow).toHaveTextContent("Unrealised -$20.");
    expect(ethRow).toHaveTextContent("Unrealised percent -10.00%.");
    expect(solRow).toHaveTextContent("Unrealised $0.");
    expect(solRow).toHaveTextContent("Unrealised percent 0.00%.");
    expect(screen.getByText("Unrealised total +$10.")).toBeInTheDocument();
    expect(screen.queryByText(/Unrealised total .*0\.00%/)).not.toBeInTheDocument();
    expect(
      screen.getAllByText(
        "Unrealised from the Coinbase print, as a share of the entry. Not a fill. No order is sent.",
      ).length,
    ).toBe(3);
  });

  it("keeps the row when the last trade is missing", async () => {
    printsAnd((path) => {
      if (path === "/api/v1/portfolio/positions") {
        return Promise.resolve({ positions: [position("BTC-USD", "100.00", "90.00", 1)] });
      }
      if (path.includes("/BTC-USD/ticker")) {
        return Promise.reject(new Error("down"));
      }
      return undefined;
    });

    renderOverview();

    const row = (await screen.findByRole("heading", { name: "BTC-USD" })).closest("li");
    expect(row).toHaveTextContent("Entry 100.00");
    expect(row).toHaveTextContent("Unrealised is unavailable.");
    expect(row).toHaveTextContent("Distance to stop is unavailable.");
    expect(row).toHaveTextContent("Unrealised percent is unavailable.");
    expect(row).not.toHaveTextContent("Unrealised percent +");
    expect(row).not.toHaveTextContent("Unrealised percent 0.00%.");
    expect(screen.getByText("Unrealised total is incomplete.")).toBeInTheDocument();
  });
});

const FIXED_NOW = Date.parse("2026-11-08T05:40:00.000Z");

describe("overview print age", () => {
  beforeEach(() => {
    vi.mocked(apiGet).mockReset();
    vi.spyOn(Date, "now").mockReturnValue(FIXED_NOW);
  });

  afterEach(() => {
    vi.mocked(Date.now).mockRestore();
  });

  it("keeps a 21-second-old price, stays quiet at 5 seconds, and does not call an unreadable time fresh", async () => {
    printsAnd((path) => {
      if (path === "/api/v1/portfolio/positions") {
        return Promise.resolve({ positions: [] });
      }
      if (path.includes("/BTC-USD/ticker")) {
        return Promise.resolve({
          ...btc,
          trade_time: "2026-11-08T05:39:39.000000000Z",
        });
      }
      if (path.includes("/ETH-USD/ticker")) {
        return Promise.resolve({
          ...eth,
          trade_time: "2026-11-08T05:39:55.000Z",
        });
      }
      if (path.includes("/SOL-USD/ticker")) {
        return Promise.resolve({
          ...sol,
          trade_time: "2026-11-08Tnot-readableZ",
        });
      }
      return undefined;
    });

    renderOverview();

    const btcCard = card("BTC-USD last trade");
    expect(await screen.findByText("$75,818.84")).toBeInTheDocument();
    expect(btcCard).toHaveTextContent("$75,818.84");
    expect(btcCard).toHaveTextContent("Exchange time 2026-11-08T05:39:39.000000000Z");
    expect(btcCard).toHaveTextContent("Print is stale. Age 21 seconds.");

    const ethCard = card("ETH-USD last trade");
    expect(ethCard).toHaveTextContent("$2,234.56");
    expect(ethCard).toHaveTextContent("Exchange time 2026-11-08T05:39:55.000Z");
    expect(ethCard).not.toHaveTextContent("Print is stale");
    expect(ethCard).not.toHaveTextContent("Exchange time is unreadable.");

    const solCard = card("SOL-USD last trade");
    expect(solCard).toHaveTextContent("$186.42");
    expect(solCard).toHaveTextContent("Exchange time is unreadable.");
    expect(solCard).not.toHaveTextContent("Print is stale");
  });
});
