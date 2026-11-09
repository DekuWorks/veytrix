import { useEffect, useRef, useState, type FormEvent } from "react";
import { ApiError, apiGet, apiPost, errorDetail } from "../api/client";
import {
  COINBASE_PRODUCTS,
  type CoinbaseProduct,
  type PaperPositionResponse,
  type SizeResponse,
  type TickerResponse,
} from "../api/types";
import { STOPS_NOT_ENFORCED } from "../content";
import { printStatus } from "../market/freshness";
import { SPREAD_NOTE, spreadLine } from "../market/spread";
import { PLANNED_RISK_PERCENT_NOTE, plannedRiskPercentLine } from "../paper/plannedRisk";
import { STOP_DISTANCE_NOTE, stopDistanceLine } from "../paper/stopDistance";

const PRODUCTS = COINBASE_PRODUCTS;
const TICKER_MS = 2_000;

type PrintState =
  | { status: "loading" }
  | { status: "unavailable" }
  | { status: "ready"; price: string; tradeTime: string; bid: string; ask: string };

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

export function RiskPage() {
  const [product, setProduct] = useState<CoinbaseProduct>("BTC-USD");
  const [equity, setEquity] = useState("");
  const [entry, setEntry] = useState("");
  const [stop, setStop] = useState("");
  const [printState, setPrintState] = useState<PrintState>({ status: "loading" });
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SizeResponse | null>(null);
  const [sizedAt, setSizedAt] = useState<{ product: CoinbaseProduct; exchangeTime: string | null } | null>(
    null,
  );
  const [recordNote, setRecordNote] = useState<string | null>(null);
  const [entryEdited, setEntryEdited] = useState(false);
  const entryEditedRef = useRef(false);
  const calcGeneration = useRef(0);

  useEffect(() => {
    document.title = "Risk · Veytrix";
  }, []);

  useEffect(() => {
    let cancelled = false;
    const load = () => {
      apiGet<TickerResponse>(`/api/v1/market/instruments/${product}/ticker`)
        .then((payload) => {
          if (cancelled) {
            return;
          }
          if (!isLivePrint(payload, product)) {
            setPrintState({ status: "unavailable" });
            if (!entryEditedRef.current) {
              setEntry("");
            }
            return;
          }
          setPrintState({
            status: "ready",
            price: payload.price,
            tradeTime: payload.trade_time,
            bid: payload.bid,
            ask: payload.ask,
          });
          if (!entryEditedRef.current) {
            setEntry(payload.price);
          }
        })
        .catch(() => {
          if (cancelled) {
            return;
          }
          setPrintState({ status: "unavailable" });
          if (!entryEditedRef.current) {
            setEntry("");
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
    calcGeneration.current += 1;
    entryEditedRef.current = false;
    setEntryEdited(false);
    setEntry("");
    setPrintState({ status: "loading" });
    setResult(null);
    setSizedAt(null);
    setRecordNote(null);
    setError(null);
    setProduct(next);
  }

  function resetEntry() {
    if (printState.status !== "ready") {
      return;
    }
    entryEditedRef.current = false;
    setEntryEdited(false);
    setEntry(printState.price);
  }

  async function recordPaper() {
    if (result === null || sizedAt === null || sizedAt.exchangeTime === null) {
      setRecordNote("The Coinbase print is unavailable. This paper size was not recorded.");
      return;
    }
    const sized = result;
    const recorded = sizedAt;
    setRecordNote(null);
    try {
      const saved = await apiPost<PaperPositionResponse>("/api/v1/portfolio/positions", {
        symbol: recorded.product,
        entry: sized.entry_price,
        stop: sized.stop_price,
        shares: sized.shares,
        notional: sized.notional,
        planned_risk: sized.planned_risk_amount,
        binding_constraint: sized.binding_constraint,
        exchange_time: recorded.exchangeTime,
      });
      if (saved.execution_permitted !== false || saved.order_submitted !== false) {
        setRecordNote("Refusing to keep a row that claims execution is permitted. No order was submitted.");
        return;
      }
      setRecordNote("Recorded on this machine. No order is sent.");
    } catch (caught) {
      if (caught instanceof ApiError) {
        setRecordNote(
          errorDetail(caught.body) ??
            "The paper position store is unavailable. This paper size was not recorded.",
        );
        return;
      }
      setRecordNote("The paper position store is unavailable. This paper size was not recorded.");
    }
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const generation = calcGeneration.current;
    const sizedProduct = product;
    const exchangeTime = printState.status === "ready" ? printState.tradeTime : null;
    setPending(true);
    setError(null);
    setResult(null);
    setSizedAt(null);
    setRecordNote(null);
    try {
      const payload = await apiPost<SizeResponse>("/api/v1/risk/size", {
        symbol: sizedProduct,
        account_equity: equity.trim(),
        entry_price: entry.trim(),
        stop_price: stop.trim(),
        side: "long",
      });
      if (generation !== calcGeneration.current) {
        return;
      }
      if (payload.execution_permitted !== false || payload.order_submitted !== false) {
        setError("Refusing to display a result that claims execution is permitted. No order was submitted.");
        return;
      }
      setSizedAt({ product: sizedProduct, exchangeTime });
      setResult(payload);
    } catch (caught) {
      if (generation !== calcGeneration.current) {
        return;
      }
      if (caught instanceof ApiError) {
        setError(errorDetail(caught.body) ?? "The risk API rejected the inputs. No order was submitted.");
        return;
      }
      setError("Risk API is unavailable. No order was submitted.");
    } finally {
      setPending(false);
    }
  }

  const live = printState.status === "ready" ? printState : null;
  const liveStatus = live === null ? null : printStatus(live.tradeTime, Date.now());

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Risk</h1>
        <p className="mt-2 max-w-3xl text-sm text-muted">
          Long only. Entry starts as the selected Coinbase last trade and keeps updating until you
          edit it. The form calculates a paper share count. No order is sent.
        </p>
      </div>
      <p id="risk-warning" role="note" className="max-w-3xl rounded-md border border-warn/40 bg-panel p-4 text-sm text-warn">
        {STOPS_NOT_ENFORCED}
      </p>
      <dl className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-md border border-line bg-panel p-3">
          <dt className="text-muted">Example per-trade risk</dt>
          <dd>0.5% of equity</dd>
        </div>
        <div className="rounded-md border border-line bg-panel p-3">
          <dt className="text-muted">Example daily stop</dt>
          <dd>1%, stored only</dd>
        </div>
        <div className="rounded-md border border-line bg-panel p-3">
          <dt className="text-muted">Example weekly stop</dt>
          <dd>3%, stored only</dd>
        </div>
        <div className="rounded-md border border-line bg-panel p-3">
          <dt className="text-muted">Example max allocation</dt>
          <dd>10% of equity</dd>
        </div>
      </dl>
      <form aria-describedby="risk-warning" className="grid max-w-xl gap-4" onSubmit={onSubmit}>
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
        <label className="grid gap-1 text-sm">
          Account equity
          <input
            className="rounded-md border border-line bg-obsidian px-3 py-2 font-mono"
            inputMode="decimal"
            autoComplete="off"
            name="account_equity"
            value={equity}
            onChange={(event) => setEquity(event.target.value)}
            placeholder="100000.00"
            required
          />
        </label>
        <label className="grid gap-1 text-sm">
          Entry price
          <input
            className="rounded-md border border-line bg-obsidian px-3 py-2 font-mono"
            inputMode="decimal"
            autoComplete="off"
            name="entry_price"
            value={entry}
            onChange={(event) => {
              entryEditedRef.current = true;
              setEntryEdited(true);
              setEntry(event.target.value);
            }}
            placeholder={printState.status === "unavailable" ? "Print unavailable" : "Waiting for Coinbase"}
            required
          />
        </label>
        <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
          {printState.status === "loading" ? (
            <p className="text-muted">Waiting for the {product} print.</p>
          ) : null}
          {printState.status === "unavailable" ? (
            <p className="text-danger" role="alert">
              Live {product} print is unavailable. No entry price was invented.
            </p>
          ) : null}
          {live ? (
            <p className="text-jade-2">
              {entryEdited
                ? `Live ${product} print ${live.price}. Exchange time ${live.tradeTime}.`
                : `Exchange time ${live.tradeTime}. Coinbase ${product} last trade.`}
            </p>
          ) : null}
          {liveStatus !== null && liveStatus.state !== "current" ? (
            <p className="text-warn">{liveStatus.line}</p>
          ) : null}
          {live ? (
            <div className="basis-full">
              <p>{spreadLine(live.bid, live.ask)}</p>
              <p className="text-warn">{SPREAD_NOTE}</p>
            </div>
          ) : null}
          <button
            type="button"
            className="rounded-md border border-line px-3 py-2 text-sm disabled:opacity-60"
            onClick={resetEntry}
            disabled={live === null}
          >
            Reset to live print
          </button>
        </div>
        <label className="grid gap-1 text-sm">
          Stop price
          <input
            className="rounded-md border border-line bg-obsidian px-3 py-2 font-mono"
            inputMode="decimal"
            autoComplete="off"
            name="stop_price"
            value={stop}
            onChange={(event) => setStop(event.target.value)}
            required
          />
        </label>
        <p className="text-sm">{stopDistanceLine(entry, stop)}</p>
        <p className="text-sm text-warn">{STOP_DISTANCE_NOTE}</p>
        <p className="text-sm text-muted">
          The server policy supplies the fractions. A risk fraction above 0.02 is rejected. The
          stop must be below the entry. No order is sent.
        </p>
        <button
          type="submit"
          className="w-fit rounded-md bg-jade px-4 py-2 text-sm font-semibold text-obsidian disabled:opacity-60"
          disabled={pending}
        >
          {pending ? "Calculating" : "Calculate paper size"}
        </button>
      </form>
      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}
      {result ? (
        <dl className="grid max-w-xl gap-2 rounded-md border border-line bg-panel p-4 text-sm">
          <div className="flex justify-between gap-4">
            <dt>Shares</dt>
            <dd className="font-mono">{result.shares}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt>Binding constraint</dt>
            <dd className="font-mono">{result.binding_constraint}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt>Planned risk</dt>
            <dd className="font-mono">{result.planned_risk_amount}</dd>
          </div>
          <p>{plannedRiskPercentLine(result.planned_risk_amount, result.account_equity)}</p>
          <p className="text-warn">{PLANNED_RISK_PERCENT_NOTE}</p>
          <div className="flex justify-between gap-4">
            <dt>Notional</dt>
            <dd className="font-mono">{result.notional}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt>Execution permitted</dt>
            <dd className="font-mono">false</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt>Order submitted</dt>
            <dd className="font-mono">false</dd>
          </div>
          <p>No order is sent.</p>
          {result.warning ? <p className="text-warn">{result.warning}</p> : null}
          <p className="text-warn">{result.note}</p>
        </dl>
      ) : null}
      {result ? (
        <div className="grid max-w-xl gap-2">
          <button
            type="button"
            className="w-fit rounded-md border border-line px-4 py-2 text-sm"
            onClick={recordPaper}
          >
            Record paper position
          </button>
          <p className="text-sm text-muted">
            Saves this paper size in the local database. It is not a fill. No order is sent.
          </p>
          {recordNote ? <p className="text-sm">{recordNote}</p> : null}
        </div>
      ) : null}
    </div>
  );
}
