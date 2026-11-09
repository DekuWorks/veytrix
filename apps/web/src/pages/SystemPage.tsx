import { useEffect, useState } from "react";
import { apiGet } from "../api/client";
import type { MarketHealthResponse, SystemStatusResponse } from "../api/types";

const SYSTEM_UNAVAILABLE = "System status is unavailable. No broker balance was invented.";
const MARKET_UNAVAILABLE = "Market health is unavailable. No substitute price was generated.";
const MONEY = /^(?:0|[1-9]\d*)(?:\.\d+)?$/;
const STAMP = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/;
const FEED_ORDER = ["BTC-USD", "ETH-USD", "SOL-USD"] as const;

type SystemState =
  | { status: "loading" }
  | { status: "unavailable" }
  | { status: "ready"; payload: SystemStatusResponse };

type MarketState =
  | { status: "loading" }
  | { status: "unavailable" }
  | { status: "ready"; payload: MarketHealthResponse };

function isSystem(value: SystemStatusResponse): boolean {
  return (
    value.status === "ok" &&
    value.env === "local" &&
    value.trading_mode === "paper" &&
    value.live_broker === "disabled" &&
    value.auth === "not_configured" &&
    value.database === "up" &&
    value.execution_permitted === false &&
    value.order_submitted === false &&
    value.order_route === "absent" &&
    value.agents_can_trade === false &&
    value.sample_data === true &&
    Number.isInteger(value.agents_registered) &&
    value.agents_registered >= 0
  );
}

function isFeed(value: MarketHealthResponse["feeds"][number], symbol: string): boolean {
  if (value.symbol !== symbol || value.synthetic !== false || value.source_id !== "coinbase-exchange") {
    return false;
  }
  if (value.note.length === 0) {
    return false;
  }
  if (value.status === "down") {
    return value.price === null && value.retrieved_at === null && value.age_seconds === null;
  }
  return (
    (value.status === "up" || value.status === "stale") &&
    value.price !== null &&
    MONEY.test(value.price) &&
    value.retrieved_at !== null &&
    STAMP.test(value.retrieved_at) &&
    value.age_seconds !== null &&
    Number.isInteger(value.age_seconds) &&
    value.age_seconds >= 0
  );
}

function expectedStatus(feeds: MarketHealthResponse["feeds"]): MarketHealthResponse["status"] {
  if (feeds.every((feed) => feed.status === "up")) {
    return "ok";
  }
  if (feeds.every((feed) => feed.status === "down")) {
    return "unavailable";
  }
  return "degraded";
}

function isMarket(value: MarketHealthResponse): boolean {
  return (
    value.source === "coinbase-exchange" &&
    value.stale_after_seconds === 120 &&
    value.sample_included === false &&
    value.executable === false &&
    value.execution_permitted === false &&
    value.order_submitted === false &&
    value.order_route === "absent" &&
    value.feeds.length === 3 &&
    value.feeds.every((feed, index) => isFeed(feed, FEED_ORDER[index])) &&
    value.status === expectedStatus(value.feeds) &&
    value.note.length > 0
  );
}

export function SystemPage() {
  const [system, setSystem] = useState<SystemState>({ status: "loading" });
  const [market, setMarket] = useState<MarketState>({ status: "loading" });

  useEffect(() => {
    document.title = "System health · Veytrix";
  }, []);

  useEffect(() => {
    let cancelled = false;
    apiGet<SystemStatusResponse>("/api/v1/system/status")
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setSystem(isSystem(payload) ? { status: "ready", payload } : { status: "unavailable" });
      })
      .catch(() => {
        if (!cancelled) {
          setSystem({ status: "unavailable" });
        }
      });
    apiGet<MarketHealthResponse>("/api/v1/market/health")
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setMarket(isMarket(payload) ? { status: "ready", payload } : { status: "unavailable" });
      })
      .catch(() => {
        if (!cancelled) {
          setMarket({ status: "unavailable" });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const posture = system.status === "ready" ? system.payload : null;
  const feeds = market.status === "ready" ? market.payload : null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">System health</h1>
        <p className="mt-2 max-w-3xl text-sm text-muted">
          This page reads the local process and the public Coinbase tickers. It cannot enable a
          desk, change a setting, or send an order.
        </p>
      </div>
      <section aria-labelledby="local-posture" className="space-y-4">
        <h2 id="local-posture" className="text-lg font-semibold">
          Local posture
        </h2>
        {system.status === "loading" ? <p className="text-sm text-muted">Loading system status.</p> : null}
        {system.status === "unavailable" ? (
          <p className="text-sm text-danger" role="alert">
            {SYSTEM_UNAVAILABLE}
          </p>
        ) : null}
        {posture ? (
          <dl className="grid max-w-xl gap-3 rounded-md border border-line bg-panel p-4 text-sm">
            <div className="flex justify-between gap-4">
              <dt>Environment</dt>
              <dd className="font-mono">{posture.env}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>Database</dt>
              <dd className="font-mono">{posture.database}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>Live broker</dt>
              <dd className="font-mono">{posture.live_broker}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>Order route</dt>
              <dd className="font-mono">{posture.order_route}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>Desks registered</dt>
              <dd className="font-mono">{posture.agents_registered}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>Desks can trade</dt>
              <dd className="font-mono">{String(posture.agents_can_trade)}</dd>
            </div>
          </dl>
        ) : null}
      </section>
      <section aria-labelledby="market-feeds" className="space-y-4">
        <h2 id="market-feeds" className="text-lg font-semibold">
          Market feeds. Not an order path. No substitute price is shown.
        </h2>
        {market.status === "loading" ? <p className="text-sm text-muted">Loading market health.</p> : null}
        {market.status === "unavailable" ? (
          <p className="text-sm text-danger" role="alert">
            {MARKET_UNAVAILABLE}
          </p>
        ) : null}
        {feeds ? (
          <>
            <p className="text-sm text-muted">
              Overall {feeds.status}. A print older than {feeds.stale_after_seconds} seconds is
              stale.
            </p>
            <ul className="max-w-xl space-y-3">
              {feeds.feeds.map((feed) => (
                <li key={feed.symbol} className="rounded-md border border-line bg-panel p-4 text-sm">
                  <p className="font-semibold">
                    {feed.symbol}{" "}
                    <span className="font-mono font-normal text-muted">{feed.status}</span>
                  </p>
                  {feed.status === "down" ? (
                    <p className="mt-2 text-danger">{feed.note}</p>
                  ) : (
                    <p className="mt-2 font-mono">
                      {feed.price}
                      {feed.status === "stale" ? " stale" : ""}
                    </p>
                  )}
                </li>
              ))}
            </ul>
            <p className="max-w-3xl text-sm text-muted">{feeds.note}</p>
          </>
        ) : null}
      </section>
    </div>
  );
}
