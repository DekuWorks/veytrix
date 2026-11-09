import { useEffect, useState } from "react";
import { apiDelete, apiGet } from "../api/client";
import {
  COINBASE_PRODUCTS,
  type CoinbaseProduct,
  type PaperPositionListResponse,
  type PaperPositionResponse,
  type TickerResponse,
} from "../api/types";
import { STOPS_NOT_ENFORCED } from "../content";
import { printStatus } from "../market/freshness";
import {
  UNREALISED_PERCENT_NOTE,
  distanceToStop,
  formatDifferenceUsd,
  formatUsd,
  unrealisedDifference,
  unrealisedPercentLine,
} from "../paper/positions";

const TICKER_MS = 2_000;

type MarkState =
  | { status: "loading" }
  | { status: "unavailable" }
  | { status: "ready"; price: string; tradeTime: string };

function isLivePrint(payload: TickerResponse, product: CoinbaseProduct): boolean {
  return (
    payload.symbol === product &&
    payload.venue === "COINBASE" &&
    payload.source_id === "coinbase-exchange" &&
    payload.synthetic === false &&
    payload.price.length > 0 &&
    payload.trade_time.includes("T")
  );
}

type ListState =
  | { status: "loading" }
  | { status: "unavailable" }
  | { status: "ready"; positions: PaperPositionResponse[] };

function isStoredRow(value: PaperPositionResponse): boolean {
  return (
    (COINBASE_PRODUCTS as readonly string[]).includes(value.symbol) &&
    value.execution_permitted === false &&
    value.order_submitted === false &&
    value.exchange_time.includes("T") &&
    value.recorded_at.includes("T")
  );
}

function productsIn(positions: readonly PaperPositionResponse[]): CoinbaseProduct[] {
  const seen = new Set<CoinbaseProduct>();
  for (const position of positions) {
    seen.add(position.symbol);
  }
  return [...seen];
}

function rowMark(position: PaperPositionResponse, mark: MarkState | undefined) {
  if (mark === undefined || mark.status === "loading") {
    return { kind: "loading" as const };
  }
  if (mark.status !== "ready") {
    return { kind: "unavailable" as const };
  }
  const difference = unrealisedDifference(mark.price, position.entry, position.shares);
  const last = formatUsd(mark.price);
  const differenceText = difference === null ? null : formatDifferenceUsd(difference);
  if (last === null || differenceText === null) {
    return { kind: "unavailable" as const };
  }
  return {
    kind: "ready" as const,
    last,
    price: mark.price,
    differenceText,
    tradeTime: mark.tradeTime,
  };
}

export function PortfolioPage() {
  const [list, setList] = useState<ListState>({ status: "loading" });
  const [removeNote, setRemoveNote] = useState<string | null>(null);
  const [marks, setMarks] = useState<Partial<Record<CoinbaseProduct, MarkState>>>({});
  const positions = list.status === "ready" ? list.positions : [];
  const productKey = productsIn(positions).join(",");

  useEffect(() => {
    document.title = "Portfolio · Veytrix";
  }, []);

  useEffect(() => {
    let cancelled = false;
    apiGet<PaperPositionListResponse>("/api/v1/portfolio/positions")
      .then((payload) => {
        if (cancelled) {
          return;
        }
        if (!Array.isArray(payload.positions) || payload.positions.some((row) => !isStoredRow(row))) {
          setList({ status: "unavailable" });
          return;
        }
        setList({ status: "ready", positions: payload.positions });
      })
      .catch(() => {
        if (!cancelled) {
          setList({ status: "unavailable" });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const products = productKey.length === 0 ? [] : (productKey.split(",") as CoinbaseProduct[]);
    if (products.length === 0) {
      return undefined;
    }
    let cancelled = false;
    const load = () => {
      for (const product of products) {
        apiGet<TickerResponse>(`/api/v1/market/instruments/${product}/ticker`)
          .then((payload) => {
            if (cancelled) {
              return;
            }
            if (!isLivePrint(payload, product)) {
              setMarks((current) => ({ ...current, [product]: { status: "unavailable" } }));
              return;
            }
            setMarks((current) => ({
              ...current,
              [product]: {
                status: "ready",
                price: payload.price,
                tradeTime: payload.trade_time,
              },
            }));
          })
          .catch(() => {
            if (!cancelled) {
              setMarks((current) => ({ ...current, [product]: { status: "unavailable" } }));
            }
          });
      }
    };
    load();
    const timer = window.setInterval(load, TICKER_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [productKey]);

  async function remove(id: string) {
    setRemoveNote(null);
    try {
      await apiDelete(`/api/v1/portfolio/positions/${id}`);
    } catch {
      setRemoveNote("The paper position store is unavailable. This row was not removed.");
      return;
    }
    setList((current) =>
      current.status === "ready"
        ? { status: "ready", positions: current.positions.filter((position) => position.id !== id) }
        : current,
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Portfolio</h1>
        <p className="mt-2 max-w-3xl text-sm text-muted">
          Paper records stored in the local database on this machine. Each row is a saved size, not a
          fill and not a brokerage position. No order is sent.
        </p>
      </div>
      <p role="note" className="max-w-3xl rounded-md border border-warn/40 bg-panel p-4 text-sm text-warn">
        {STOPS_NOT_ENFORCED}
      </p>
      {removeNote ? <p className="text-sm text-danger">{removeNote}</p> : null}
      {list.status === "loading" ? <p className="text-sm text-muted">Loading paper positions.</p> : null}
      {list.status === "unavailable" ? (
        <p className="text-sm text-danger" role="alert">
          Paper positions are unavailable. No row was invented.
        </p>
      ) : null}
      {list.status === "ready" && positions.length === 0 ? (
        <p className="text-sm text-muted">No paper positions recorded yet.</p>
      ) : null}
      {list.status === "ready" && positions.length > 0 ? (
        <ul className="grid max-w-3xl gap-3">
          {positions.map((position) => {
            const mark = rowMark(position, marks[position.symbol]);
            const distance = mark.kind === "ready" ? distanceToStop(mark.price, position.stop) : null;
            const freshness = mark.kind === "ready" ? printStatus(mark.tradeTime, Date.now()) : null;
            return (
              <li key={position.id} className="rounded-md border border-line bg-panel p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h2 className="text-base font-semibold">{position.symbol}</h2>
                    <p className="text-sm text-muted">Paper</p>
                  </div>
                  <button
                    type="button"
                    className="rounded-md border border-line px-3 py-1 text-sm"
                    onClick={() => remove(position.id)}
                  >
                    Remove
                  </button>
                </div>
                <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                  <div className="flex justify-between gap-4">
                    <dt>Entry</dt>
                    <dd className="font-mono">{position.entry}</dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt>Stop</dt>
                    <dd className="font-mono">{position.stop}</dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt>Shares</dt>
                    <dd className="font-mono">{position.shares}</dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt>Notional</dt>
                    <dd className="font-mono">{position.notional}</dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt>Planned risk</dt>
                    <dd className="font-mono">{position.planned_risk}</dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt>Binding constraint</dt>
                    <dd className="font-mono">{position.binding_constraint}</dd>
                  </div>
                </dl>
                <p className="mt-3 text-xs text-muted">
                  Exchange time of the print {position.exchange_time}. Recorded at {position.recorded_at}.
                </p>
                <div className="mt-3 text-sm">
                  <p>Mark from the Coinbase print. Not a fill.</p>
                  {mark.kind === "loading" ? (
                    <p className="text-muted">Waiting for the Coinbase print.</p>
                  ) : null}
                  {mark.kind === "unavailable" ? <p>Mark unavailable</p> : null}
                  {mark.kind === "ready" ? (
                    <p>
                      Last trade {mark.last}. Unrealised {mark.differenceText} USD. Mark time{" "}
                      {mark.tradeTime}.
                    </p>
                  ) : null}
                  {freshness !== null && freshness.state !== "current" ? <p>{freshness.line}</p> : null}
                  <p>Distance to stop from the Coinbase print. The stop is not enforced.</p>
                  {mark.kind === "loading" ? (
                    <p className="text-muted">Distance to stop is loading.</p>
                  ) : null}
                  {mark.kind !== "loading" && distance === null ? (
                    <p>Distance to stop is unavailable.</p>
                  ) : null}
                  {distance !== null ? (
                    <p>
                      Distance to stop {distance.usd} ({distance.percent}).
                    </p>
                  ) : null}
                  <p className="text-warn">{UNREALISED_PERCENT_NOTE}</p>
                  {mark.kind === "loading" ? <p className="text-muted">Unrealised percent is loading.</p> : null}
                  {mark.kind === "unavailable" ? <p>Unrealised percent is unavailable.</p> : null}
                  {mark.kind === "ready" ? <p>{unrealisedPercentLine(mark.price, position.entry)}</p> : null}
                </div>
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}
