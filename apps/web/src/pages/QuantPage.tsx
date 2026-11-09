import { useEffect, useState } from "react";
import { apiGet } from "../api/client";
import {
  COINBASE_PRODUCTS,
  type BarResponse,
  type BarsResponse,
  type CoinbaseProduct,
  type TickerResponse,
} from "../api/types";
import { KpiCard } from "../components/KpiCard";
import { printAverageGapLine, printMinusAverage } from "../market/averageGap";
import { candleAge } from "../market/candleAge";
import { printGapLine, printMinusClose } from "../market/printGap";
import { windowPosition, windowPositionLine } from "../market/windowPosition";
import { CLOSE_AVERAGE_WINDOW, averageOfLastCloses } from "../quant/average";

const PRODUCTS = COINBASE_PRODUCTS;
const TICKER_MS = 2_000;
const MINUTE_MS = 45_000;
const MINUTE_LIMIT = 180;

type PrintState = { status: "loading" } | { status: "unavailable" } | { status: "ready"; price: string };

type Figures = {
  lastClose: number;
  latestClose: string;
  highest: number;
  lowest: number;
  windowHigh: string;
  windowLow: string;
  average: number | null;
  distanceUsd: number | null;
  distancePercent: number | null;
};

type QuantState =
  | { status: "loading" }
  | { status: "unavailable" }
  | { status: "unreadable"; retrievedAt: string; lastClose: string; barStart: string }
  | { status: "ready"; retrievedAt: string; barStart: string; close: string; figures: Figures };

function isPrint(payload: TickerResponse, product: CoinbaseProduct): boolean {
  return (
    payload.symbol === product &&
    payload.source_id === "coinbase-exchange" &&
    payload.synthetic === false &&
    typeof payload.price === "string" &&
    payload.price.length > 0 &&
    typeof payload.trade_time === "string" &&
    payload.trade_time.includes("T")
  );
}

function isCoinbaseMinute(payload: BarsResponse, product: CoinbaseProduct): boolean {
  return (
    payload.symbol === product &&
    payload.source_id === "coinbase-exchange" &&
    payload.synthetic === false &&
    payload.interval === "1m" &&
    payload.last_close !== null &&
    payload.retrieved_at !== null &&
    payload.retrieved_at.includes("T")
  );
}

function positive(value: number): boolean {
  return Number.isFinite(value) && value > 0;
}

function summarise(bars: readonly BarResponse[]): Figures | null {
  if (bars.length === 0) {
    return null;
  }
  const closes: number[] = [];
  let latestClose = "";
  let windowHigh = "";
  let windowLow = "";
  let highest = Number.NEGATIVE_INFINITY;
  let lowest = Number.POSITIVE_INFINITY;
  let previousTime = Number.NEGATIVE_INFINITY;
  for (const bar of bars) {
    const open = Number(bar.open);
    const high = Number(bar.high);
    const low = Number(bar.low);
    const close = Number(bar.close);
    if (![open, high, low, close].every(positive)) {
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
    if (time <= previousTime) {
      return null;
    }
    previousTime = time;
    closes.push(close);
    latestClose = bar.close;
    if (high > highest) {
      highest = high;
      windowHigh = bar.high;
    }
    if (low < lowest) {
      lowest = low;
      windowLow = bar.low;
    }
  }
  const lastClose = closes.at(-1);
  if (lastClose === undefined || !Number.isFinite(highest) || !Number.isFinite(lowest)) {
    return null;
  }
  if (closes.length < CLOSE_AVERAGE_WINDOW) {
    return {
      lastClose,
      latestClose,
      highest,
      lowest,
      windowHigh,
      windowLow,
      average: null,
      distanceUsd: null,
      distancePercent: null,
    };
  }
  const average = averageOfLastCloses(closes);
  if (average === null) {
    return null;
  }
  const distanceUsd = lastClose - average;
  return {
    lastClose,
    latestClose,
    highest,
    lowest,
    windowHigh,
    windowLow,
    average,
    distanceUsd,
    distancePercent: (distanceUsd / average) * 100,
  };
}

function usd(value: number): string {
  const negative = value < 0;
  const [whole, fraction] = Math.abs(value).toFixed(2).split(".");
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `${negative ? "-" : ""}$${grouped}.${fraction}`;
}

function signedUsd(value: number): string {
  if (value > 0) {
    return `+${usd(value)}`;
  }
  return usd(value);
}

function labelledPrice(value: string): string {
  const [whole, fraction = "00"] = value.split(".");
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `$${grouped}.${fraction.slice(0, 2).padEnd(2, "0")}`;
}

function signedPercent(value: number): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function decimalFromComputedAverage(value: number): string | null {
  if (!Number.isFinite(value) || value < 0) {
    return null;
  }
  const text = value.toFixed(8).replace(/0+$/, "").replace(/\.$/, "");
  return /^\d+(?:\.\d+)?$/.test(text) ? text : null;
}

function averageGapLine(print: PrintState, average: number): string {
  if (print.status === "loading") {
    return "Print minus average is loading.";
  }
  if (print.status !== "ready") {
    return "Print minus average is unavailable.";
  }
  const averageText = decimalFromComputedAverage(average);
  if (averageText === null) {
    return "Print minus average is unavailable.";
  }
  return printAverageGapLine(printMinusAverage(print.price, averageText));
}

function quantGap(print: PrintState, state: QuantState): string {
  if (print.status === "loading" || state.status === "loading") {
    return "Print minus candle is loading.";
  }
  const close = state.status === "ready" ? state.close : state.status === "unreadable" ? state.lastClose : null;
  if (print.status !== "ready" || close === null) {
    return "Print minus candle is unavailable.";
  }
  return printGapLine(printMinusClose(print.price, close));
}

export function QuantPage() {
  const [product, setProduct] = useState<CoinbaseProduct>("BTC-USD");
  const [state, setState] = useState<QuantState>({ status: "loading" });
  const [print, setPrint] = useState<PrintState>({ status: "loading" });

  useEffect(() => {
    document.title = "Quant · Veytrix";
  }, []);

  useEffect(() => {
    let cancelled = false;
    const load = () => {
      apiGet<BarsResponse>(`/api/v1/market/instruments/${product}/bars?interval=1m&limit=${MINUTE_LIMIT}`)
        .then((payload) => {
          if (cancelled) {
            return;
          }
          if (!isCoinbaseMinute(payload, product) || payload.retrieved_at === null) {
            setState({ status: "unavailable" });
            return;
          }
          const latest = payload.bars.at(-1)?.bar_start ?? "";
          const figures = summarise(payload.bars);
          if (figures === null) {
            if (candleAge(latest, Date.now()).state === "unreadable" && payload.last_close !== null) {
              setState({
                status: "unreadable",
                retrievedAt: payload.retrieved_at,
                lastClose: payload.last_close,
                barStart: latest,
              });
              return;
            }
            setState({ status: "unavailable" });
            return;
          }
          if (payload.last_close === null) {
            setState({ status: "unavailable" });
            return;
          }
          setState({
            status: "ready",
            retrievedAt: payload.retrieved_at,
            barStart: latest,
            close: payload.last_close,
            figures,
          });
        })
        .catch(() => {
          if (!cancelled) {
            setState({ status: "unavailable" });
          }
        });
    };
    load();
    const timer = window.setInterval(load, MINUTE_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [product]);

  useEffect(() => {
    let cancelled = false;
    const load = () => {
      apiGet<TickerResponse>(`/api/v1/market/instruments/${product}/ticker`)
        .then((payload) => {
          if (cancelled) {
            return;
          }
          setPrint(isPrint(payload, product) ? { status: "ready", price: payload.price } : { status: "unavailable" });
        })
        .catch(() => {
          if (!cancelled) {
            setPrint({ status: "unavailable" });
          }
        });
    };
    load();
    const timer = window.setInterval(load, TICKER_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [product]);

  function selectProduct(next: CoinbaseProduct) {
    if (next === product) {
      return;
    }
    setState({ status: "loading" });
    setPrint({ status: "loading" });
    setProduct(next);
  }

  const figures = state.status === "ready" ? state.figures : null;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Quant</h1>
          <p className="mt-2 max-w-3xl text-sm text-muted">
            Calculated from Coinbase 1-minute candles. Not a trading signal. Not a consolidated
            quote. No order is sent.
          </p>
        </div>
        <fieldset className="flex flex-wrap items-center gap-2 border-0 p-0">
          <legend className="mr-1 text-sm text-muted">Product</legend>
          {PRODUCTS.map((id) => (
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
      </div>
      {state.status === "loading" ? (
        <p className="text-sm text-muted">Loading {product} 1-minute candles.</p>
      ) : null}
      {state.status === "unavailable" ? (
        <p className="rounded-md border border-danger/40 bg-panel p-4 text-sm text-danger" role="alert">
          1-minute candles are unavailable. No figures were invented.
        </p>
      ) : null}
      {print.status === "ready" ? (
        <p className="font-mono text-sm">Last trade {labelledPrice(print.price)}.</p>
      ) : null}
      <p className="text-sm">{quantGap(print, state)}</p>
      {state.status === "ready" || state.status === "unreadable" ? (
        <div className="space-y-2">
          <p className="font-mono text-xs text-jade-2">As of {state.retrievedAt}</p>
          <p className="font-mono text-xs text-jade-2">Bar start (UTC) {state.barStart}.</p>
          <p className="text-sm">{candleAge(state.barStart, Date.now()).line}</p>
        </div>
      ) : null}
      {state.status === "unreadable" ? (
        <KpiCard label="Last 1-minute close" value={usd(Number(state.lastClose))} detail={product} />
      ) : null}
      {figures ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <KpiCard label="Last 1-minute close" value={usd(figures.lastClose)} detail={product} />
            <KpiCard label="Highest high" value={usd(figures.highest)} detail="Loaded window" />
            <KpiCard label="Lowest low" value={usd(figures.lowest)} detail="Loaded window" />
            {figures.average !== null ? (
              <KpiCard label="20-bar average" value={usd(figures.average)} detail="Last 20 closes" />
            ) : null}
          </div>
          {figures.average === null ? (
            <p className="text-sm text-muted">There are not enough bars for a 20-bar average.</p>
          ) : (
            <>
              <p className="text-sm">
                {windowPositionLine(windowPosition(figures.latestClose, figures.windowHigh, figures.windowLow))}
              </p>
              <p className="text-sm">{averageGapLine(print, figures.average)}</p>
            </>
          )}
          {figures.distanceUsd !== null && figures.distancePercent !== null ? (
            <KpiCard
              label="Distance from the 20-bar average"
              value={signedUsd(figures.distanceUsd)}
              detail={`${signedPercent(figures.distancePercent)} of the average`}
            />
          ) : null}
        </>
      ) : null}
    </div>
  );
}
