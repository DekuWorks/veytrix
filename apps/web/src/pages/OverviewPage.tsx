import { useEffect, useState } from "react";
import { ApiError, apiGet } from "../api/client";
import {
  COINBASE_PRODUCTS,
  type BarsResponse,
  type CoinbaseProduct,
  type DiagnosticsResponse,
  type HealthResponse,
  type PaperPositionListResponse,
  type PaperPositionResponse,
  type ReadyResponse,
  type TickerResponse,
} from "../api/types";
import { KpiCard } from "../components/KpiCard";
import { lastSizeLine, volumeLine } from "../market/baseQuantity";
import { dayRangeLine, inProgressDayRange } from "../market/dayRange";
import { currentDayBounds, dayPosition, dayPositionLine } from "../market/dayPosition";
import { printStatus } from "../market/freshness";
import { spreadLine } from "../market/spread";
import {
  distanceToStop,
  formatDifferenceUsd,
  sumSignedDecimals,
  unrealisedDifference,
  unrealisedPercentLine,
} from "../paper/positions";

type Probe =
  | { status: "loading" }
  | { status: "error" }
  | {
      status: "ready";
      health: HealthResponse;
      readiness: ReadyResponse;
      diagnostics: DiagnosticsResponse;
    };

const TICKER_MS = 2_000;
const DAILY_MS = 45_000;
const BOOK_MS = 15_000;

type QuoteState = { status: "loading" } | { status: "unavailable" } | { status: "ready"; payload: TickerResponse };

type DailyState =
  | { status: "loading" }
  | { status: "unavailable" }
  | {
      status: "ready";
      change: string | null;
      changePercent: string | null;
      rangeLine: string;
      high: string | null;
      low: string | null;
    };

const SIGNED_DECIMAL = /^(?:\+|-)?\d+(?:\.\d+)?$/;

function isLivePrint(payload: TickerResponse, product: CoinbaseProduct): boolean {
  return (
    payload.symbol === product &&
    payload.venue === "COINBASE" &&
    payload.source_id === "coinbase-exchange" &&
    payload.synthetic === false &&
    payload.price.length > 0 &&
    payload.bid.length > 0 &&
    payload.ask.length > 0 &&
    payload.trade_time.includes("T")
  );
}

function isDailyChange(payload: BarsResponse, product: CoinbaseProduct): boolean {
  return (
    payload.symbol === product &&
    payload.venue === "COINBASE" &&
    payload.source_id === "coinbase-exchange" &&
    payload.synthetic === false &&
    payload.interval === "1d" &&
    payload.change !== null &&
    payload.change_percent !== null &&
    SIGNED_DECIMAL.test(payload.change) &&
    SIGNED_DECIMAL.test(payload.change_percent)
  );
}

function displaySignedUsd(value: string): string {
  const sign = value.startsWith("+") || value.startsWith("-") ? value[0] : "";
  const unsigned = sign === "" ? value : value.slice(1);
  const [whole, fraction] = unsigned.split(".");
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const digits = fraction === undefined ? grouped : `${grouped}.${fraction}`;
  if (sign === "+") {
    return `+$${digits}`;
  }
  if (sign === "-") {
    return `-$${digits}`;
  }
  return `$${digits}`;
}

function isDailyPayload(payload: BarsResponse, product: CoinbaseProduct): boolean {
  return (
    payload.symbol === product &&
    payload.venue === "COINBASE" &&
    payload.source_id === "coinbase-exchange" &&
    payload.synthetic === false &&
    payload.interval === "1d"
  );
}

function dailyNote(state: DailyState): string {
  if (state.status === "ready" && state.change !== null && state.changePercent !== null) {
    return `${displaySignedUsd(state.change)} (${state.changePercent}%) versus the previous daily close.`;
  }
  if (state.status === "loading") {
    return "Daily change versus the previous daily close is loading.";
  }
  return "Daily change versus the previous daily close is unavailable.";
}

function rangeNote(state: DailyState): string {
  if (state.status === "loading") {
    return "Day range is loading.";
  }
  if (state.status === "unavailable") {
    return "Day range is unavailable.";
  }
  return state.rangeLine;
}

function positionNote(quote: QuoteState, state: DailyState): string {
  if (quote.status === "loading" || state.status === "loading") {
    return "Position in the day is loading.";
  }
  if (quote.status !== "ready" || state.status !== "ready" || state.high === null || state.low === null) {
    return "Position in the day is unavailable.";
  }
  return dayPositionLine(dayPosition(quote.payload.price, state.high, state.low));
}

function printDetail(payload: TickerResponse, now: number): string {
  const base = `Bid ${usd(payload.bid)} · ask ${usd(payload.ask)}. Exchange time ${payload.trade_time}.`;
  const status = printStatus(payload.trade_time, now);
  const head = status.state === "current" ? base : `${base} ${status.line}`;
  return `${head} ${spreadLine(payload.bid, payload.ask)}`;
}

function baseAsset(product: CoinbaseProduct): string {
  return product.slice(0, product.indexOf("-"));
}

function tickerActivity(payload: TickerResponse): string {
  const asset = baseAsset(payload.symbol);
  return `${volumeLine(payload.volume, asset)} ${lastSizeLine(payload.size, asset)}`;
}

function usd(value: string): string {
  const [whole, fraction = "00"] = value.split(".");
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `$${grouped}.${fraction.slice(0, 2).padEnd(2, "0")}`;
}

type BookState =
  | { status: "loading" }
  | { status: "unavailable" }
  | { status: "ready"; positions: PaperPositionResponse[] };

function isStoredRow(value: PaperPositionResponse): boolean {
  return (
    (COINBASE_PRODUCTS as readonly string[]).includes(value.symbol) &&
    value.execution_permitted === false &&
    value.order_submitted === false &&
    Number.isSafeInteger(value.shares) &&
    value.shares >= 0 &&
    value.entry.length > 0 &&
    value.stop.length > 0
  );
}

type RowFigures =
  | { kind: "loading" }
  | { kind: "unavailable" }
  | { kind: "ready"; unrealised: string; unrealisedText: string; distanceUsd: string; distancePercent: string };

function rowFigures(position: PaperPositionResponse, quote: QuoteState): RowFigures {
  if (quote.status === "loading") {
    return { kind: "loading" };
  }
  if (quote.status !== "ready") {
    return { kind: "unavailable" };
  }
  const unrealised = unrealisedDifference(quote.payload.price, position.entry, position.shares);
  const unrealisedText = unrealised === null ? null : formatDifferenceUsd(unrealised);
  const distance = distanceToStop(quote.payload.price, position.stop);
  if (unrealised === null || unrealisedText === null || distance === null) {
    return { kind: "unavailable" };
  }
  return {
    kind: "ready",
    unrealised,
    unrealisedText,
    distanceUsd: distance.usd,
    distancePercent: distance.percent,
  };
}

function bookTotal(figures: readonly RowFigures[]): string {
  if (figures.some((figure) => figure.kind === "unavailable")) {
    return "Unrealised total is incomplete.";
  }
  if (figures.some((figure) => figure.kind === "loading")) {
    return "Unrealised total is loading.";
  }
  const values = figures.flatMap((figure) => (figure.kind === "ready" ? [figure.unrealised] : []));
  const sum = sumSignedDecimals(values);
  const text = sum === null ? null : formatDifferenceUsd(sum);
  if (text === null) {
    return "Unrealised total is incomplete.";
  }
  return `Unrealised total ${text}.`;
}

function isReadyBody(body: unknown): body is ReadyResponse {
  if (typeof body !== "object" || body === null) {
    return false;
  }
  const record = body as Record<string, unknown>;
  return (
    (record.status === "ready" || record.status === "unavailable") &&
    (record.database === "up" || record.database === "down")
  );
}

export function OverviewPage() {
  const [probe, setProbe] = useState<Probe>({ status: "loading" });
  const [quotes, setQuotes] = useState<Record<CoinbaseProduct, QuoteState>>({
    "BTC-USD": { status: "loading" },
    "ETH-USD": { status: "loading" },
    "SOL-USD": { status: "loading" },
  });
  const [daily, setDaily] = useState<Record<CoinbaseProduct, DailyState>>({
    "BTC-USD": { status: "loading" },
    "ETH-USD": { status: "loading" },
    "SOL-USD": { status: "loading" },
  });
  const [book, setBook] = useState<BookState>({ status: "loading" });

  useEffect(() => {
    document.title = "Overview · Veytrix";
  }, []);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      apiGet<HealthResponse>("/api/v1/health"),
      apiGet<ReadyResponse>("/api/v1/ready").catch((error: unknown) => {
        if (error instanceof ApiError && error.status === 503 && isReadyBody(error.body)) {
          return error.body;
        }
        throw error;
      }),
      apiGet<DiagnosticsResponse>("/api/v1/diagnostics"),
    ])
      .then(([health, readiness, diagnostics]) => {
        if (!cancelled) {
          setProbe({ status: "ready", health, readiness, diagnostics });
        }
      })
      .catch(() => {
        if (!cancelled) {
          setProbe({ status: "error" });
        }
      });
    const loadQuotes = () => {
      for (const product of COINBASE_PRODUCTS) {
        apiGet<TickerResponse>(`/api/v1/market/instruments/${product}/ticker`)
          .then((payload) => {
            if (cancelled) {
              return;
            }
            setQuotes((current) => ({
              ...current,
              [product]: isLivePrint(payload, product)
                ? { status: "ready", payload }
                : { status: "unavailable" },
            }));
          })
          .catch(() => {
            if (!cancelled) {
              setQuotes((current) => ({ ...current, [product]: { status: "unavailable" } }));
            }
          });
      }
    };
    loadQuotes();
    const timer = window.setInterval(loadQuotes, TICKER_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    const loadDaily = () => {
      for (const product of COINBASE_PRODUCTS) {
        apiGet<BarsResponse>(`/api/v1/market/instruments/${product}/bars?interval=1d&limit=2`)
          .then((payload) => {
            if (cancelled) {
              return;
            }
            if (!isDailyPayload(payload, product)) {
              setDaily((current) => ({ ...current, [product]: { status: "unavailable" } }));
              return;
            }
            const changeReady =
              isDailyChange(payload, product) && payload.change !== null && payload.change_percent !== null;
            const bounds = currentDayBounds(payload.bars);
            setDaily((current) => ({
              ...current,
              [product]: {
                status: "ready",
                change: changeReady ? payload.change : null,
                changePercent: changeReady ? payload.change_percent : null,
                rangeLine: dayRangeLine(inProgressDayRange(payload.bars)),
                high: bounds?.high ?? null,
                low: bounds?.low ?? null,
              },
            }));
          })
          .catch(() => {
            if (!cancelled) {
              setDaily((current) => ({ ...current, [product]: { status: "unavailable" } }));
            }
          });
      }
    };
    loadDaily();
    const timer = window.setInterval(loadDaily, DAILY_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    const loadBook = () => {
      apiGet<PaperPositionListResponse>("/api/v1/portfolio/positions")
        .then((payload) => {
          if (cancelled) {
            return;
          }
          if (!Array.isArray(payload.positions) || payload.positions.some((row) => !isStoredRow(row))) {
            setBook({ status: "unavailable" });
            return;
          }
          setBook({ status: "ready", positions: payload.positions });
        })
        .catch(() => {
          if (!cancelled) {
            setBook({ status: "unavailable" });
          }
        });
    };
    loadBook();
    const timer = window.setInterval(loadBook, BOOK_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  const positions = book.status === "ready" ? book.positions : [];
  const figures = positions.map((position) => rowFigures(position, quotes[position.symbol]));
  const now = Date.now();

  return (
    <div className="vx-page">
      <div>
        <h1 className="vx-title">Overview</h1>
        <p className="vx-lede">
          Local posture for this build. The cards below describe the code that is running, not a
          live brokerage account.
        </p>
      </div>
      <section aria-labelledby="build-posture">
        <h2 id="build-posture" className="vx-section-title">
          This build
        </h2>
        <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <KpiCard label="Orders" value="Not sent" detail="No broker is connected." />
          <KpiCard label="Live broker" value="Disabled" detail="The API refuses to boot if enabled." />
          <KpiCard label="Authentication" value="Not configured" detail="Loopback binding is not a login." />
        </div>
      </section>
      <section aria-labelledby="live-prints">
        <h2 id="live-prints" className="vx-section-title">
          Live prints
        </h2>
        <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {COINBASE_PRODUCTS.map((product) => {
            const quote = quotes[product];
            const ready = quote.status === "ready" ? quote.payload : null;
            return (
              <KpiCard
                key={product}
                label={`${product} last trade`}
                value={ready ? usd(ready.price) : quote.status === "unavailable" ? "Unavailable" : "Loading"}
                detail={
                  ready
                    ? printDetail(ready, now)
                    : quote.status === "unavailable"
                      ? "No price was invented."
                      : "Waiting for the Coinbase print."
                }
                activity={ready ? tickerActivity(ready) : undefined}
                note={dailyNote(daily[product])}
                extra={rangeNote(daily[product])}
                position={positionNote(quote, daily[product])}
              />
            );
          })}
        </div>
      </section>
      <section aria-labelledby="paper-book">
        <h2 id="paper-book" className="vx-section-title">
          Paper book
        </h2>
        {book.status === "loading" ? <p className="mt-3 text-sm text-muted">Loading the paper book.</p> : null}
        {book.status === "unavailable" ? (
          <p className="vx-alert mt-3" role="alert">
            The paper book is unavailable.
          </p>
        ) : null}
        {book.status === "ready" && positions.length === 0 ? (
          <p className="mt-3 text-sm text-muted">No paper positions recorded yet.</p>
        ) : null}
        {book.status === "ready" && positions.length > 0 ? (
          <>
            <ul className="mt-4 grid max-w-3xl gap-3">
              {positions.map((position, index) => {
                const figure = figures[index];
                const quote = quotes[position.symbol];
                const freshness = quote.status === "ready" ? printStatus(quote.payload.trade_time, now) : null;
                return (
                  <li key={position.id} className="vx-card text-sm">
                    <h3 className="text-base font-semibold">{position.symbol}</h3>
                    <p className="mt-2">
                      Shares <span className="font-mono">{position.shares}</span>
                    </p>
                    <p>
                      Entry <span className="font-mono">{position.entry}</span>
                    </p>
                    {figure?.kind === "loading" ? <p className="text-muted">Unrealised is loading.</p> : null}
                    {figure?.kind === "unavailable" ? <p>Unrealised is unavailable.</p> : null}
                    {figure?.kind === "ready" ? <p>Unrealised {figure.unrealisedText}.</p> : null}
                    {figure?.kind === "loading" ? <p className="text-muted">Distance to stop is loading.</p> : null}
                    {figure?.kind === "unavailable" ? <p>Distance to stop is unavailable.</p> : null}
                    {figure?.kind === "ready" ? (
                      <p>
                        Distance to stop {figure.distanceUsd} ({figure.distancePercent}).
                      </p>
                    ) : null}
                    {figure?.kind === "loading" ? <p className="text-muted">Unrealised percent is loading.</p> : null}
                    {figure?.kind === "unavailable" ? <p>Unrealised percent is unavailable.</p> : null}
                    {figure?.kind === "ready" ? (
                      <p>{unrealisedPercentLine(quote.status === "ready" ? quote.payload.price : "", position.entry)}</p>
                    ) : null}
                    {freshness !== null && freshness.state !== "current" ? <p>{freshness.line}</p> : null}
                  </li>
                );
              })}
            </ul>
            <p className="mt-3 text-sm">{bookTotal(figures)}</p>
          </>
        ) : null}
      </section>
      <section aria-labelledby="api-probe" className="vx-card">
        <h2 id="api-probe" className="vx-section-title">
          API probe
        </h2>
        {probe.status === "loading" ? <p className="mt-3 text-sm text-muted">Checking the local API.</p> : null}
        {probe.status === "error" ? (
          <p className="vx-alert mt-3" role="alert">
            API probe failed. No status was invented.
          </p>
        ) : null}
        {probe.status === "ready" ? (
          <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-muted">Health</dt>
              <dd className="font-mono">{probe.health.status}</dd>
            </div>
            <div>
              <dt className="text-muted">Readiness</dt>
              <dd className="font-mono">
                {probe.readiness.status} · database {probe.readiness.database}
              </dd>
            </div>
            <div>
              <dt className="text-muted">Diagnostics auth</dt>
              <dd className="font-mono">{probe.diagnostics.auth}</dd>
            </div>
            <div>
              <dt className="text-muted">API version</dt>
              <dd className="font-mono">{probe.diagnostics.versions.api}</dd>
            </div>
          </dl>
        ) : null}
      </section>
    </div>
  );
}
