import { useEffect, useState } from "react";
import { apiGet } from "../api/client";
import type {
  PaperSwapOrder,
  PaperSwapOrderListResponse,
  PaperSwapPortfolioResponse,
} from "../api/types";
import { PAPER_SWAP_NOTICE } from "../content";

const LEDGER_DOWN = "The paper-swap ledger is unavailable.";
const EMPTY_BALANCES = "No simulated balances yet. The paper-swap CLI records them.";
const EMPTY_ORDERS = "No simulated swaps yet.";

type PortfolioState =
  | { status: "loading" }
  | { status: "unavailable" }
  | { status: "ready"; portfolio: PaperSwapPortfolioResponse };

type OrderState =
  | { status: "loading" }
  | { status: "unavailable" }
  | { status: "ready"; orders: PaperSwapOrder[] };

function isMoney(value: string): boolean {
  return value.length > 0 && !value.includes("e") && !value.includes("E");
}

function isPortfolio(value: PaperSwapPortfolioResponse): boolean {
  return (
    value.simulated === true &&
    value.execution_permitted === false &&
    value.order_submitted === false &&
    Array.isArray(value.networks) &&
    value.networks.every(
      (network) =>
        network.simulated === true &&
        network.balances.every((balance) => isMoney(balance.amount) && balance.symbol.length > 0),
    )
  );
}

function isOrder(value: PaperSwapOrder): boolean {
  return (
    value.simulated === true &&
    value.status === "simulated" &&
    value.execution_permitted === false &&
    value.order_submitted === false &&
    value.quote_source.length > 0 &&
    value.created_at.includes("T") &&
    isMoney(value.amount_in) &&
    isMoney(value.amount_out) &&
    (value.price_kind === "pool" || value.price_kind === "reference")
  );
}

function priceLabel(order: PaperSwapOrder): string {
  if (order.price_kind === "reference") {
    return "Reference price";
  }
  return "Pool quote";
}

export function PaperSwapsPage() {
  const [portfolio, setPortfolio] = useState<PortfolioState>({ status: "loading" });
  const [orders, setOrders] = useState<OrderState>({ status: "loading" });

  useEffect(() => {
    document.title = "Paper swaps · Veytrix";
  }, []);

  useEffect(() => {
    let cancelled = false;
    apiGet<PaperSwapPortfolioResponse>("/api/v1/paper-swaps/portfolio")
      .then((payload) => {
        if (cancelled) {
          return;
        }
        if (!isPortfolio(payload)) {
          setPortfolio({ status: "unavailable" });
          return;
        }
        setPortfolio({ status: "ready", portfolio: payload });
      })
      .catch(() => {
        if (!cancelled) {
          setPortfolio({ status: "unavailable" });
        }
      });
    apiGet<PaperSwapOrderListResponse>("/api/v1/paper-swaps/orders")
      .then((payload) => {
        if (cancelled) {
          return;
        }
        if (
          payload.simulated !== true ||
          payload.execution_permitted !== false ||
          payload.order_submitted !== false ||
          !payload.orders.every(isOrder)
        ) {
          setOrders({ status: "unavailable" });
          return;
        }
        setOrders({ status: "ready", orders: payload.orders });
      })
      .catch(() => {
        if (!cancelled) {
          setOrders({ status: "unavailable" });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm font-semibold text-jade">Simulated</p>
        <h1 className="mt-1 text-2xl font-semibold">Paper swaps</h1>
        <p className="mt-2 max-w-3xl text-sm text-muted">{PAPER_SWAP_NOTICE}</p>
      </div>

      <section aria-label="Simulated balances" className="space-y-3">
        <h2 className="text-lg font-semibold">Balances</h2>
        {portfolio.status === "loading" ? <p className="text-sm text-muted">Loading balances.</p> : null}
        {portfolio.status === "unavailable" ? <p className="text-sm text-muted">{LEDGER_DOWN}</p> : null}
        {portfolio.status === "ready" && portfolio.portfolio.networks.length === 0 ? (
          <p className="text-sm text-muted">{EMPTY_BALANCES}</p>
        ) : null}
        {portfolio.status === "ready" && portfolio.portfolio.networks.length > 0 ? (
          <table className="w-full border-collapse text-sm">
            <caption className="sr-only">Simulated balances</caption>
            <thead>
              <tr className="border-b border-line text-left text-muted">
                <th className="py-2 pr-4 font-medium">Chain</th>
                <th className="py-2 pr-4 font-medium">Token</th>
                <th className="py-2 font-medium">Amount</th>
              </tr>
            </thead>
            <tbody>
              {portfolio.portfolio.networks.flatMap((network) =>
                network.balances.map((balance) => (
                  <tr key={`${network.chain}-${balance.symbol}`} className="border-b border-line">
                    <td className="py-2 pr-4">
                      {network.chain} · {network.network}
                    </td>
                    <td className="py-2 pr-4">{balance.symbol}</td>
                    <td className="py-2">{balance.amount}</td>
                  </tr>
                )),
              )}
            </tbody>
          </table>
        ) : null}
      </section>

      <section aria-label="Simulated swaps" className="space-y-3">
        <h2 className="text-lg font-semibold">Swaps</h2>
        {orders.status === "loading" ? <p className="text-sm text-muted">Loading swaps.</p> : null}
        {orders.status === "unavailable" ? <p className="text-sm text-muted">{LEDGER_DOWN}</p> : null}
        {orders.status === "ready" && orders.orders.length === 0 ? (
          <p className="text-sm text-muted">{EMPTY_ORDERS}</p>
        ) : null}
        {orders.status === "ready" && orders.orders.length > 0 ? (
          <table className="w-full border-collapse text-sm">
            <caption className="sr-only">Simulated swaps</caption>
            <thead>
              <tr className="border-b border-line text-left text-muted">
                <th className="py-2 pr-4 font-medium">Pair</th>
                <th className="py-2 pr-4 font-medium">In</th>
                <th className="py-2 pr-4 font-medium">Out</th>
                <th className="py-2 pr-4 font-medium">Price</th>
                <th className="py-2 font-medium">Fee</th>
              </tr>
            </thead>
            <tbody>
              {orders.orders.map((order) => (
                <tr key={order.id} className="border-b border-line">
                  <td className="py-2 pr-4">
                    {order.token_in} to {order.token_out}
                    <span className="mt-1 block text-muted">
                      Simulated · {order.chain} · {priceLabel(order)}
                    </span>
                  </td>
                  <td className="py-2 pr-4">
                    {order.amount_in} {order.token_in}
                  </td>
                  <td className="py-2 pr-4">
                    {order.amount_out} {order.token_out}
                  </td>
                  <td className="py-2 pr-4">{order.quote_source}</td>
                  <td className="py-2">
                    {order.fee_estimate} {order.fee_symbol}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
      </section>
    </div>
  );
}
