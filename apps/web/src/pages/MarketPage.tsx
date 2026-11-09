import { useEffect, useRef, useState } from "react";
import { apiGet } from "../api/client";
import {
  COINBASE_PRODUCTS,
  type BarResponse,
  type BarsResponse,
  type CoinbaseProduct,
  type TickerResponse,
} from "../api/types";
import { KpiCard } from "../components/KpiCard";
import { SampleChart, type ChartBar } from "../components/SampleChart";
import { TICKER_SIZE_NOTE, formatBaseQuantity } from "../market/baseQuantity";
import { CANDLE_AGE_NOTE, candleAge } from "../market/candleAge";
import { DAY_POSITION_NOTE, currentDayBounds, dayPosition, dayPositionLine } from "../market/dayPosition";
import { PRINT_GAP_NOTE, printGapLine, printMinusClose } from "../market/printGap";
import { printStatus } from "../market/freshness";
import { SPREAD_NOTE, spreadLine } from "../market/spread";

const PRICE = /^\d+(?:\.\d+)?$/;
const TICKER_MS = 2_000;
const MINUTE_MS = 45_000;
const DAILY_MS = 15 * 60_000;
const MINUTE_LIMIT = 180;
const DAILY_LIMIT = 14;

type SeriesState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "invalid" }
  | { status: "ready"; payload: BarsResponse };

type MinuteState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "invalid" }
  | { status: "ready"; payload: BarsResponse; plotted: ChartBar[] };

type TickerState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "invalid" }
  | { status: "ready"; payload: TickerResponse };

function isTicker(payload: TickerResponse, product: CoinbaseProduct): boolean {
  return (
    payload.symbol === product &&
    payload.source_id === "coinbase-exchange" &&
    payload.synthetic === false &&
    payload.price.length > 0 &&
    payload.trade_time.includes("T")
  );
}

function isCoinbaseSeries(
  payload: BarsResponse,
  interval: "1m" | "1d",
  product: CoinbaseProduct,
): boolean {
  return (
    payload.symbol === product &&
    payload.source_id === "coinbase-exchange" &&
    payload.synthetic === false &&
    payload.interval === interval &&
    payload.last_close !== null &&
    payload.retrieved_at !== null &&
    payload.retrieved_at.includes("T")
  );
}

function baseAsset(product: CoinbaseProduct): string {
  return product.slice(0, product.indexOf("-"));
}

function toMinuteBars(bars: readonly BarResponse[]): ChartBar[] | null {
  const plotted: ChartBar[] = [];
  for (const bar of bars) {
    const open = Number(bar.open);
    const high = Number(bar.high);
    const low = Number(bar.low);
    const close = Number(bar.close);
    if (![open, high, low, close].every((value) => Number.isFinite(value) && value > 0)) {
      return null;
    }
    if (high < Math.max(open, close) || low > Math.min(open, close)) {
      return null;
    }
    const millis = Date.parse(bar.bar_start);
    if (!Number.isFinite(millis)) {
      return null;
    }
    const time = Math.floor(millis / 1000);
    const previous = plotted.at(-1)?.time;
    if (typeof previous === "number" && time <= previous) {
      return null;
    }
    plotted.push({ time, open, high, low, close, volume: bar.volume });
  }
  return plotted.length > 0 ? plotted : null;
}

type Attempt<T> = { state: "value"; value: T } | { state: "stale" } | { state: "failed" };

async function requestWithOneRetry<T>(path: string, stale: () => boolean): Promise<Attempt<T>> {
  try {
    return { state: "value", value: await apiGet<T>(path) };
  } catch {
    if (stale()) {
      return { state: "stale" };
    }
    try {
      return { state: "value", value: await apiGet<T>(path) };
    } catch {
      return stale() ? { state: "stale" } : { state: "failed" };
    }
  }
}

function candleGap(ticker: TickerState, minute: MinuteState): string {
  if (ticker.status === "loading" || minute.status === "loading") {
    return "Print minus candle is loading.";
  }
  if (ticker.status !== "ready" || minute.status !== "ready" || minute.payload.last_close === null) {
    return "Print minus candle is unavailable.";
  }
  return printGapLine(printMinusClose(ticker.payload.price, minute.payload.last_close));
}

function marketPosition(ticker: TickerState, daily: SeriesState): string {
  if (ticker.status === "loading" || daily.status === "loading") {
    return "Position in the day is loading.";
  }
  if (ticker.status !== "ready" || daily.status !== "ready") {
    return "Position in the day is unavailable.";
  }
  const bounds = currentDayBounds(daily.payload.bars);
  if (bounds === null) {
    return "Position in the day is unavailable.";
  }
  return dayPositionLine(dayPosition(ticker.payload.price, bounds.high, bounds.low));
}

function decimalUnits(value: string): { units: bigint; scale: number } | null {
  if (!PRICE.test(value)) {
    return null;
  }
  const [whole, fraction = ""] = value.split(".");
  return { units: BigInt(`${whole}${fraction}`), scale: fraction.length };
}

function dayLines(
  high: string | null | undefined,
  low: string | null | undefined,
): { high: string | null; low: string | null } {
  const highPrice = high != null && decimalUnits(high) !== null ? high : null;
  const lowPrice = low != null && decimalUnits(low) !== null ? low : null;
  if (highPrice === null || lowPrice === null) {
    return { high: highPrice, low: lowPrice };
  }
  const highScaled = decimalUnits(highPrice);
  const lowScaled = decimalUnits(lowPrice);
  if (highScaled === null || lowScaled === null) {
    return { high: highPrice, low: lowPrice };
  }
  const scale = Math.max(highScaled.scale, lowScaled.scale);
  const highUnits = highScaled.units * 10n ** BigInt(scale - highScaled.scale);
  const lowUnits = lowScaled.units * 10n ** BigInt(scale - lowScaled.scale);
  if (highUnits < lowUnits) {
    return { high: null, low: null };
  }
  return { high: highPrice, low: lowPrice };
}

function usd(value: string | null): string {
  if (value === null) {
    return "—";
  }
  const negative = value.startsWith("-");
  const unsigned = negative ? value.slice(1) : value;
  const [whole, fraction = "00"] = unsigned.split(".");
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `${negative ? "-" : ""}$${grouped}.${fraction.slice(0, 2).padEnd(2, "0")}`;
}

function signedUsd(value: string | null): string {
  if (value === null) {
    return "—";
  }
  if (value.startsWith("+")) {
    return `+${usd(value.slice(1))}`;
  }
  if (value.startsWith("-")) {
    return `-${usd(value.slice(1))}`;
  }
  return usd(value);
}

export function MarketPage() {
  const [product, setProduct] = useState<CoinbaseProduct>("BTC-USD");
  const [attempt, setAttempt] = useState(0);
  const [minute, setMinute] = useState<MinuteState>({ status: "loading" });
  const [daily, setDaily] = useState<SeriesState>({ status: "loading" });
  const [previousClose, setPreviousClose] = useState<string | null>(null);
  const [dayHigh, setDayHigh] = useState<string | null>(null);
  const [dayLow, setDayLow] = useState<string | null>(null);
  const [ticker, setTicker] = useState<TickerState>({ status: "loading" });
  const requestGeneration = useRef(0);

  function selectProduct(next: CoinbaseProduct) {
    if (next === product) {
      return;
    }
    requestGeneration.current += 1;
    setMinute({ status: "loading" });
    setDaily({ status: "loading" });
    setPreviousClose(null);
    setDayHigh(null);
    setDayLow(null);
    setTicker({ status: "loading" });
    setProduct(next);
  }

  useEffect(() => {
    document.title = "Market · Veytrix";
  }, []);

  useEffect(() => {
    const generation = requestGeneration.current;
    let cancelled = false;
    const stale = () => cancelled || requestGeneration.current !== generation;
    const load = () => {
      const path = `/api/v1/market/instruments/${product}/bars?interval=1m&limit=${MINUTE_LIMIT}`;
      void requestWithOneRetry<BarsResponse>(path, stale).then((result) => {
        if (stale() || result.state === "stale") {
          return;
        }
        if (result.state === "failed") {
          setMinute((current) => (current.status === "ready" ? current : { status: "error" }));
          return;
        }
        const payload = result.value;
        if (!isCoinbaseSeries(payload, "1m", product)) {
          setMinute((current) => (current.status === "ready" ? current : { status: "invalid" }));
          return;
        }
        const plotted = toMinuteBars(payload.bars);
        if (plotted === null) {
          const latest = payload.bars.at(-1)?.bar_start ?? "";
          if (candleAge(latest, Date.now()).state !== "unreadable") {
            setMinute((current) => (current.status === "ready" ? current : { status: "invalid" }));
            return;
          }
          setMinute({ status: "ready", payload, plotted: [] });
          return;
        }
        setMinute({ status: "ready", payload, plotted });
      });
    };
    load();
    const timer = window.setInterval(load, MINUTE_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [attempt, product]);

  useEffect(() => {
    const generation = requestGeneration.current;
    let cancelled = false;
    const stale = () => cancelled || requestGeneration.current !== generation;
    const load = () => {
      const path = `/api/v1/market/instruments/${product}/bars?interval=1d&limit=${DAILY_LIMIT}`;
      void requestWithOneRetry<BarsResponse>(path, stale).then((result) => {
        if (stale() || result.state === "stale") {
          return;
        }
        if (result.state === "failed") {
          setDayHigh(null);
          setDayLow(null);
          setDaily((current) => (current.status === "ready" ? current : { status: "error" }));
          return;
        }
        const payload = result.value;
        if (!isCoinbaseSeries(payload, "1d", product)) {
          setPreviousClose(null);
          setDayHigh(null);
          setDayLow(null);
          setDaily({ status: "invalid" });
          return;
        }
        const bounds = currentDayBounds(payload.bars);
        const lines = dayLines(bounds?.high, bounds?.low);
        setPreviousClose(payload.previous_close);
        setDayHigh(lines.high);
        setDayLow(lines.low);
        setDaily({ status: "ready", payload });
      });
    };
    load();
    const timer = window.setInterval(load, DAILY_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [attempt, product]);

  useEffect(() => {
    const generation = requestGeneration.current;
    let cancelled = false;
    const stale = () => cancelled || requestGeneration.current !== generation;
    const load = () => {
      const path = `/api/v1/market/instruments/${product}/ticker`;
      void requestWithOneRetry<TickerResponse>(path, stale).then((result) => {
        if (stale() || result.state === "stale") {
          return;
        }
        if (result.state === "failed") {
          setTicker((current) => (current.status === "ready" ? current : { status: "error" }));
          return;
        }
        const payload = result.value;
        setTicker(isTicker(payload, product) ? { status: "ready", payload } : { status: "invalid" });
      });
    };
    load();
    const timer = window.setInterval(load, TICKER_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [attempt, product]);

  const changeClass =
    daily.status === "ready" && daily.payload.change?.startsWith("-") ? "text-danger" : "text-jade-2";
  const recentMinutes = minute.status === "ready" ? minute.payload.bars.slice(-8) : [];
  const base = baseAsset(product);
  const print =
    ticker.status === "ready" ? printStatus(ticker.payload.trade_time, Date.now()) : null;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Market</h1>
          <p className="mt-2 max-w-3xl text-sm text-muted">
            The headline is the latest Coinbase trade for the selected product, refreshed every 2
            seconds. The chart is that product&apos;s 1-minute candles for the last three hours,
            refreshed about every 45 seconds. The daily table keeps the change versus the previous
            close. BTC-USD is the default. If a feed is down, nothing is invented.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <fieldset className="flex flex-wrap items-center gap-2 border-0 p-0">
            <legend className="mr-1 text-sm text-muted">Product</legend>
            {COINBASE_PRODUCTS.map((id) => (
              <button
                key={id}
                type="button"
                aria-pressed={product === id}
                className={`rounded-md border px-3 py-2 text-sm ${
                  product === id ? "border-jade-2 text-jade-2" : "border-line"
                }`}
                onClick={() => selectProduct(id)}
              >
                {id}
              </button>
            ))}
          </fieldset>
          <button
            type="button"
            className="rounded-md border border-line px-3 py-2 text-sm"
            onClick={() => {
              setMinute({ status: "loading" });
              setDaily({ status: "loading" });
              setPreviousClose(null);
              setDayHigh(null);
              setDayLow(null);
              setAttempt((value) => value + 1);
            }}
          >
            Retry
          </button>
        </div>
      </div>
      {ticker.status === "loading" ? <p className="text-sm text-muted">Waiting for the live print.</p> : null}
      {ticker.status === "error" ? (
        <p className="rounded-md border border-danger/40 bg-panel p-4 text-sm text-danger" role="alert">
          Live ticker is unavailable. No price was invented.
        </p>
      ) : null}
      {ticker.status === "invalid" ? (
        <p className="rounded-md border border-danger/40 bg-panel p-4 text-sm text-danger" role="alert">
          The ticker response was not a Coinbase {product} print.
        </p>
      ) : null}
      {ticker.status === "ready" ? (
        <section aria-labelledby="live-print" className="space-y-3">
          <div className="flex flex-wrap items-baseline justify-between gap-3">
            <h2 id="live-print" className="text-lg font-semibold">
              Live print · {ticker.payload.symbol}
            </h2>
            <p className="font-mono text-xs text-jade-2">Exchange time {ticker.payload.trade_time}</p>
          </div>
          {print !== null && print.state !== "current" ? (
            <p className="text-sm text-warn">{print.line}</p>
          ) : null}
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <KpiCard
              label="Last trade"
              value={usd(ticker.payload.price)}
              detail={`${ticker.payload.symbol} · Coinbase`}
            />
            <KpiCard label="Bid" value={usd(ticker.payload.bid)} detail="Coinbase book" />
            <KpiCard label="Ask" value={usd(ticker.payload.ask)} detail="Coinbase book" />
            <KpiCard
              label="24-hour base volume"
              value={formatBaseQuantity(ticker.payload.volume) ?? "Volume is unavailable."}
              detail={baseAsset(ticker.payload.symbol)}
            />
            <KpiCard
              label="Last trade size"
              value={formatBaseQuantity(ticker.payload.size) ?? "Last size is unavailable."}
              detail={baseAsset(ticker.payload.symbol)}
            />
          </div>
          <p className="text-sm text-warn">{TICKER_SIZE_NOTE}</p>
          <p className="text-sm">{spreadLine(ticker.payload.bid, ticker.payload.ask)}</p>
          <p className="text-sm text-warn">{SPREAD_NOTE}</p>
          <p className="text-sm">{marketPosition(ticker, daily)}</p>
          <p className="text-sm text-warn">{DAY_POSITION_NOTE}</p>
          <p className="text-sm text-warn">{ticker.payload.disclaimer}</p>
        </section>
      ) : null}

      <section aria-labelledby="minute-series" className="space-y-3">
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <h2 id="minute-series" className="text-lg font-semibold">
            {product} · 1 minute
          </h2>
          {minute.status === "ready" ? (
            <p className="font-mono text-xs text-jade-2">As of {minute.payload.retrieved_at}</p>
          ) : null}
        </div>
        <p className="text-sm">{candleGap(ticker, minute)}</p>
        <p className="text-sm text-warn">{PRINT_GAP_NOTE}</p>
        {minute.status === "loading" ? (
          <p className="text-sm text-muted">Loading {product} 1-minute candles.</p>
        ) : null}
        {minute.status === "error" ? (
          <p className="rounded-md border border-danger/40 bg-panel p-4 text-sm text-danger" role="alert">
            1-minute candles are unavailable. No price was invented.
          </p>
        ) : null}
        {minute.status === "invalid" ? (
          <p className="rounded-md border border-danger/40 bg-panel p-4 text-sm text-danger" role="alert">
            The API response was not a Coinbase {product} 1-minute series. No prices are shown.
          </p>
        ) : null}
        {minute.status === "ready" ? (
          <div className="space-y-4">
            <p className="text-sm text-warn">{minute.payload.disclaimer}</p>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <KpiCard
                label="Last 1-minute close"
                value={usd(minute.payload.last_close)}
                detail={`${minute.payload.symbol} · Coinbase · 1 minute`}
              />
              <KpiCard
                label="Interval"
                value="1 minute"
                detail="Coinbase granularity 60 seconds"
              />
            </div>
            <p className="font-mono text-xs text-jade-2">
              Bar start (UTC) {minute.payload.bars.at(-1)?.bar_start ?? "—"}.
            </p>
            <p className="text-sm">{candleAge(minute.payload.bars.at(-1)?.bar_start ?? "", Date.now()).line}</p>
            <p className="text-sm text-warn">{CANDLE_AGE_NOTE}</p>
            {minute.plotted.length > 0 ? (
            <SampleChart
              key={minute.payload.symbol}
              bars={minute.plotted}
              caption={`${minute.payload.symbol} 1-minute candles on Coinbase. Not a consolidated quote. Not investment advice. No order is sent. As of ${minute.payload.retrieved_at}. Line: 20-bar average of closes. Not a trading signal. No order is sent. Volume bars: 1-minute base volume from the Coinbase candle. Not USD. Not a trading signal. No order is sent. Horizontal line: the latest Coinbase print. It is not the candle close. No order is sent. Second line: the previous daily close. Not a settlement of today. No order is sent. Day high and day low: the in-progress UTC daily candle. Not a settlement. No order is sent.`}
              lastTrade={ticker.status === "ready" ? ticker.payload.price : null}
              previousClose={previousClose}
              dayHigh={dayHigh}
              dayLow={dayLow}
              label={`${minute.payload.symbol} 1-minute candlestick chart from Coinbase. Not a consolidated quote. Not investment advice. No order is sent.`}
            />
            ) : null}
            <div className="max-h-64 overflow-auto rounded-md border border-line">
              <table className="w-full text-left text-sm">
                <caption className="px-3 py-2 text-left text-muted">
                  Latest {minute.payload.symbol} 1-minute bars from Coinbase. Not a consolidated quote.
                  No order is sent.
                </caption>
                <thead className="sticky top-0 bg-panel-2">
                  <tr>
                    <th scope="col" className="px-3 py-2 font-medium">Bar start (UTC)</th>
                    <th scope="col" className="px-3 py-2 font-medium">Open</th>
                    <th scope="col" className="px-3 py-2 font-medium">High</th>
                    <th scope="col" className="px-3 py-2 font-medium">Low</th>
                    <th scope="col" className="px-3 py-2 font-medium">Close</th>
                    <th scope="col" className="px-3 py-2 font-medium">Volume ({base})</th>
                  </tr>
                </thead>
                <tbody>
                  {recentMinutes.map((bar) => (
                    <tr key={bar.bar_start} className="border-t border-line font-mono">
                      <td className="px-3 py-2">{bar.bar_start}</td>
                      <td className="px-3 py-2">{bar.open}</td>
                      <td className="px-3 py-2">{bar.high}</td>
                      <td className="px-3 py-2">{bar.low}</td>
                      <td className="px-3 py-2">{bar.close}</td>
                      <td className="px-3 py-2">{bar.volume}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}
      </section>

      <section aria-labelledby="daily-series" className="space-y-3">
        <h2 id="daily-series" className="text-lg font-semibold">
          Daily candles · {product}
        </h2>
        {daily.status === "loading" ? (
          <p className="text-sm text-muted">Loading {product} daily candles.</p>
        ) : null}
        {daily.status === "error" ? (
          <p className="rounded-md border border-danger/40 bg-panel p-4 text-sm text-danger" role="alert">
            Daily candles are unavailable. No price was invented.
          </p>
        ) : null}
        {daily.status === "invalid" ? (
          <p className="rounded-md border border-danger/40 bg-panel p-4 text-sm text-danger" role="alert">
            The API response was not a Coinbase {product} daily series. No prices are shown.
          </p>
        ) : null}
        {daily.status === "ready" ? (
          <div className="space-y-4">
            <p className="text-sm text-warn">{daily.payload.disclaimer}</p>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <KpiCard
                label="Last daily close"
                value={usd(daily.payload.last_close)}
                detail={daily.payload.symbol}
              />
              <article className="rounded-md border border-line bg-panel p-4">
                <h3 className="text-sm text-muted">Change vs previous close</h3>
                <p className={`mt-2 font-mono text-2xl ${changeClass}`}>{signedUsd(daily.payload.change)}</p>
                <p className={`mt-2 font-mono text-sm ${changeClass}`}>
                  {daily.payload.change_percent === null ? "—" : `${daily.payload.change_percent}%`}
                </p>
              </article>
              <article className="rounded-md border border-line bg-panel p-4">
                <h3 className="text-sm text-muted">Last daily range</h3>
                <p className="mt-2 font-mono text-lg text-ink">
                  Low {usd(daily.payload.bars.at(-1)?.low ?? null)}
                </p>
                <p className="mt-1 font-mono text-lg text-ink">
                  High {usd(daily.payload.bars.at(-1)?.high ?? null)}
                </p>
              </article>
              <KpiCard
                label="Last daily volume"
                value={daily.payload.bars.at(-1)?.volume ?? "—"}
                detail={`${base} traded on Coinbase`}
              />
            </div>
            <div className="max-h-64 overflow-auto rounded-md border border-line">
              <table className="w-full text-left text-sm">
                <caption className="px-3 py-2 text-left text-muted">
                  {daily.payload.symbol} daily candles from Coinbase. Change versus the previous daily
                  close. Not a consolidated quote. Not investment advice. No order is sent.
                </caption>
                <thead className="sticky top-0 bg-panel-2">
                  <tr>
                    <th scope="col" className="px-3 py-2 font-medium">Bar start (UTC)</th>
                    <th scope="col" className="px-3 py-2 font-medium">Open</th>
                    <th scope="col" className="px-3 py-2 font-medium">High</th>
                    <th scope="col" className="px-3 py-2 font-medium">Low</th>
                    <th scope="col" className="px-3 py-2 font-medium">Close</th>
                    <th scope="col" className="px-3 py-2 font-medium">Volume ({base})</th>
                  </tr>
                </thead>
                <tbody>
                  {daily.payload.bars.map((bar) => (
                    <tr key={bar.bar_start} className="border-t border-line font-mono">
                      <td className="px-3 py-2">{bar.bar_start}</td>
                      <td className="px-3 py-2">{bar.open}</td>
                      <td className="px-3 py-2">{bar.high}</td>
                      <td className="px-3 py-2">{bar.low}</td>
                      <td className="px-3 py-2">{bar.close}</td>
                      <td className="px-3 py-2">{bar.volume}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}
      </section>
    </div>
  );
}
