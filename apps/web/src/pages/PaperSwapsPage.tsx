import { useEffect, useState } from "react";
import { apiGet } from "../api/client";
import type {
  PaperSwapOrder,
  PaperSwapOrderListResponse,
  PaperSwapPortfolioResponse,
  PaperSwapPostureResponse,
} from "../api/types";
import { PAPER_SWAP_NOTICE } from "../content";

const LEDGER_DOWN = "The paper-swap ledger is unavailable.";
const POSTURE_DOWN = "Paper-swap posture is unavailable. No signing path was invented.";
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

type PostureState =
  | { status: "loading" }
  | { status: "unavailable" }
  | { status: "ready"; posture: PaperSwapPostureResponse };

function isPosture(value: PaperSwapPostureResponse): boolean {
  return (
    value.signing === "absent" &&
    value.broadcast === "absent" &&
    value.private_key === "refused" &&
    value.api_can_record === false &&
    value.mainnet === "refused" &&
    value.networks.join(",") === "solana-devnet,sepolia,base-sepolia" &&
    value.chain_ids.join(",") === "devnet,11155111,84532" &&
    value.executable === false &&
    value.execution_permitted === false &&
    value.order_submitted === false &&
    value.source === "local_posture" &&
    value.note.length > 0
  );
}

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
  const [posture, setPosture] = useState<PostureState>({ status: "loading" });

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
    apiGet<PaperSwapPostureResponse>("/api/v1/paper-swaps/posture")
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setPosture(isPosture(payload) ? { status: "ready", posture: payload } : { status: "unavailable" });
      })
      .catch(() => {
        if (!cancelled) {
          setPosture({ status: "unavailable" });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="vx-page">
      <div>
        <p className="text-sm font-semibold text-jade">Simulated</p>
        <h1 className="vx-title">Paper swaps</h1>
        <p className="vx-lede">{PAPER_SWAP_NOTICE}</p>
      </div>
      <section aria-label="Swap posture" className="space-y-3">
        <h2 className="vx-section-title">Signing</h2>
        {posture.status === "loading" ? <p className="text-sm text-muted">Loading posture.</p> : null}
        {posture.status === "unavailable" ? (
          <p className="vx-alert" role="alert">
            {POSTURE_DOWN}
          </p>
        ) : null}
        {posture.status === "ready" ? (
          <dl className="grid max-w-xl gap-3 vx-card text-sm">
            <div className="flex justify-between gap-4">
              <dt>Signing</dt>
              <dd className="font-mono">{posture.posture.signing}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>Broadcast</dt>
              <dd className="font-mono">{posture.posture.broadcast}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>Private key</dt>
              <dd className="font-mono">{posture.posture.private_key}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>Mainnet</dt>
              <dd className="font-mono">{posture.posture.mainnet}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>API can record</dt>
              <dd className="font-mono">{String(posture.posture.api_can_record)}</dd>
            </div>
          </dl>
        ) : null}
      </section>

      <section aria-label="Simulated balances" className="space-y-3">
        <h2 className="vx-section-title">Balances</h2>
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
        <h2 className="vx-section-title">Swaps</h2>
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
