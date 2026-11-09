import { useEffect, useState } from "react";
import { apiGet } from "../api/client";
import { COINBASE_PRODUCTS, type BarResponse, type BarsResponse, type CoinbaseProduct } from "../api/types";
import { CANDLE_AGE_NOTE, candleAge } from "../market/candleAge";
import { MOVE_AGE_NOTE, moveAgeLine } from "../market/moveAge";

const PRODUCTS = COINBASE_PRODUCTS;
const MINUTE_MS = 45_000;
const MOVE_AGE_TICK_MS = 15_000;
const MINUTE_LIMIT = 180;
const TOP_MOVES = 5;

type Move = {
  barStart: string;
  previousClose: number;
  close: number;
  changeUsd: number;
  changePercent: number;
};

type ProductState =
  | { status: "loading" }
  | { status: "unavailable" }
  | { status: "short"; barStart: string }
  | { status: "empty"; retrievedAt: string; barStart: string }
  | { status: "ready"; retrievedAt: string; barStart: string; moves: Move[] };

function isCoinbaseMinute(payload: BarsResponse, product: CoinbaseProduct): boolean {
  return (
    payload.symbol === product &&
    payload.source_id === "coinbase-exchange" &&
    payload.synthetic === false &&
    payload.interval === "1m" &&
    payload.retrieved_at !== null &&
    payload.retrieved_at.includes("T")
  );
}

function positiveClose(value: number): boolean {
  return Number.isFinite(value) && value > 0;
}

function largestMoves(bars: readonly BarResponse[]): Move[] {
  const kept: { time: number; barStart: string; close: number }[] = [];
  for (const bar of bars) {
    const close = Number(bar.close);
    if (!positiveClose(close)) {
      continue;
    }
    const time = Date.parse(bar.bar_start);
    const previous = kept.at(-1);
    if (previous !== undefined && Number.isFinite(time) && time <= previous.time) {
      continue;
    }
    kept.push({ time, barStart: bar.bar_start, close });
  }
  const moves: Move[] = [];
  for (let index = 1; index < kept.length; index += 1) {
    const previous = kept[index - 1];
    const current = kept[index];
    if (previous === undefined || current === undefined) {
      continue;
    }
    const changeUsd = current.close - previous.close;
    moves.push({
      barStart: current.barStart,
      previousClose: previous.close,
      close: current.close,
      changeUsd,
      changePercent: (changeUsd / previous.close) * 100,
    });
  }
  moves.sort((left, right) => Math.abs(right.changeUsd) - Math.abs(left.changeUsd) || right.barStart.localeCompare(left.barStart));
  return moves.slice(0, TOP_MOVES);
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

function signedPercent(value: number): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function CandleAge({ barStart }: { barStart: string }) {
  const age = candleAge(barStart, Date.now());
  return (
    <>
      {barStart.length > 0 ? <p className="font-mono text-xs text-jade-2">Bar start (UTC) {barStart}.</p> : null}
      <p className="text-sm">{age.line}</p>
      <p className="text-sm text-warn">{CANDLE_AGE_NOTE}</p>
    </>
  );
}

function ProductMoves({
  product,
  state,
  now,
}: {
  product: CoinbaseProduct;
  state: ProductState;
  now: number;
}) {
  return (
    <section aria-label={product} className="space-y-3">
      <h2 className="text-lg font-semibold">{product}</h2>
      {state.status === "loading" ? (
        <p className="text-sm text-muted">Loading {product} 1-minute candles.</p>
      ) : null}
      {state.status === "unavailable" ? (
        <p className="rounded-md border border-danger/40 bg-panel p-4 text-sm text-danger" role="alert">
          {product} is unavailable. No price was invented.
        </p>
      ) : null}
      {state.status === "short" ? (
        <>
          <CandleAge barStart={state.barStart} />
          <p className="text-sm text-muted">There are not enough bars for {product}.</p>
        </>
      ) : null}
      {state.status === "empty" ? (
        <>
          <p className="font-mono text-xs text-jade-2">As of {state.retrievedAt}</p>
          <CandleAge barStart={state.barStart} />
          <p className="text-sm text-muted">No 1-minute moves in this window.</p>
        </>
      ) : null}
      {state.status === "ready" ? (
        <>
          <p className="font-mono text-xs text-jade-2">As of {state.retrievedAt}</p>
          <CandleAge barStart={state.barStart} />
          <ol className="grid gap-3">
            {state.moves.map((move) => (
              <li key={move.barStart} className="rounded-md border border-line bg-panel p-4 text-sm">
                <p className="font-mono text-xs text-muted">Bar start {move.barStart}</p>
                <dl className="mt-3 grid gap-2 sm:grid-cols-2">
                  <div className="flex justify-between gap-4">
                    <dt>Previous close</dt>
                    <dd className="font-mono">{usd(move.previousClose)}</dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt>Close</dt>
                    <dd className="font-mono">{usd(move.close)}</dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt>Change</dt>
                    <dd className="font-mono">{signedUsd(move.changeUsd)}</dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt>Percent</dt>
                    <dd className="font-mono">{signedPercent(move.changePercent)}</dd>
                  </div>
                </dl>
                <p className="mt-3">{moveAgeLine(move.barStart, now)}</p>
                <p className="text-warn">{MOVE_AGE_NOTE}</p>
              </li>
            ))}
          </ol>
        </>
      ) : null}
    </section>
  );
}

export function EventsPage() {
  const [states, setStates] = useState<Record<CoinbaseProduct, ProductState>>({
    "BTC-USD": { status: "loading" },
    "ETH-USD": { status: "loading" },
    "SOL-USD": { status: "loading" },
  });
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    document.title = "Events · Veytrix";
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), MOVE_AGE_TICK_MS);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const loadProduct = (product: CoinbaseProduct) => {
      apiGet<BarsResponse>(`/api/v1/market/instruments/${product}/bars?interval=1m&limit=${MINUTE_LIMIT}`)
        .then((payload) => {
          if (cancelled) {
            return;
          }
          const retrievedAt = payload.retrieved_at;
          if (!isCoinbaseMinute(payload, product) || retrievedAt === null) {
            setStates((current) => ({ ...current, [product]: { status: "unavailable" } }));
            return;
          }
          const barStart = payload.bars.at(-1)?.bar_start ?? "";
          if (payload.bars.length < 2) {
            setStates((current) => ({ ...current, [product]: { status: "short", barStart } }));
            return;
          }
          const moves = largestMoves(payload.bars);
          setStates((current) => ({
            ...current,
            [product]:
              moves.length === 0
                ? { status: "empty", retrievedAt, barStart }
                : { status: "ready", retrievedAt, barStart, moves },
          }));
        })
        .catch(() => {
          if (!cancelled) {
            setStates((current) => ({ ...current, [product]: { status: "unavailable" } }));
          }
        });
    };
    const load = () => {
      for (const product of PRODUCTS) {
        loadProduct(product);
      }
    };
    load();
    const timer = window.setInterval(load, MINUTE_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Events</h1>
        <p className="mt-2 max-w-3xl text-sm text-muted">
          Detected from Coinbase 1-minute candles on this machine. Not news. Not a trading signal.
          Not a consolidated quote. No order is sent.
        </p>
      </div>
      {PRODUCTS.map((product) => (
        <ProductMoves key={product} product={product} state={states[product]} now={now} />
      ))}
    </div>
  );
}
