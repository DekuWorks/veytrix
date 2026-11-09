import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiGet } from "../api/client";
import type { PaperSwapOrder, PaperSwapPortfolioResponse } from "../api/types";
import { PAPER_SWAP_NOTICE } from "../content";
import { AppRoutes } from "../App";

vi.mock("../api/client", () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiDelete: vi.fn(),
}));

const portfolio: PaperSwapPortfolioResponse = {
  simulated: true,
  execution_permitted: false,
  order_submitted: false,
  networks: [
    {
      chain: "ethereum",
      network: "sepolia",
      chain_id: "11155111",
      simulated: true,
      balances: [
        { symbol: "ETH", amount: "0.9899" },
        { symbol: "USDC", amount: "1099.5" },
      ],
    },
  ],
};

const order: PaperSwapOrder = {
  id: "order-1",
  chain: "ethereum",
  network: "sepolia",
  chain_id: "11155111",
  token_in: "ETH",
  token_out: "USDC",
  amount_in: "0.01",
  quoted_out: "100",
  amount_out: "99.5",
  quoted_price: "10000",
  quote_source: "uniswap-v3-quoterv2-eth_call",
  price_kind: "pool",
  slippage_bps: 50,
  slippage_applied: "0.5",
  fee_estimate: "0.0001",
  fee_symbol: "ETH",
  balances_after: { ETH: "0.9899", USDC: "1099.5" },
  status: "simulated",
  simulated: true,
  created_at: "2026-11-08T18:00:00Z",
  execution_permitted: false,
  order_submitted: false,
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/paper-swaps"]}>
      <AppRoutes />
    </MemoryRouter>,
  );
}

describe("paper swaps page", () => {
  beforeEach(() => {
    vi.mocked(apiGet).mockReset();
  });

  it("shows the simulated label, balances, and a recorded swap", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.endsWith("/portfolio")) {
        return Promise.resolve(portfolio);
      }
      return Promise.resolve({
        simulated: true,
        execution_permitted: false,
        order_submitted: false,
        orders: [order],
      });
    });
    renderPage();

    expect(await screen.findByRole("heading", { name: "Paper swaps" })).toBeInTheDocument();
    expect(screen.getByText("Simulated")).toBeInTheDocument();
    expect(screen.getByText(PAPER_SWAP_NOTICE)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Paper swaps" })).toHaveAttribute("href", "/paper-swaps");
    expect(screen.getByText("0.9899")).toBeInTheDocument();
    expect(screen.getByText("ETH to USDC")).toBeInTheDocument();
    expect(screen.getByText("uniswap-v3-quoterv2-eth_call")).toBeInTheDocument();
    expect(screen.getByText(/Pool quote/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /swap|submit|broadcast/i })).not.toBeInTheDocument();
    expect(vi.mocked(apiGet)).toHaveBeenCalledWith("/api/v1/paper-swaps/portfolio");
    expect(vi.mocked(apiGet)).toHaveBeenCalledWith("/api/v1/paper-swaps/orders");
  });

  it("shows an empty ledger without inventing balances", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.endsWith("/portfolio")) {
        return Promise.resolve({
          simulated: true,
          execution_permitted: false,
          order_submitted: false,
          networks: [],
        });
      }
      return Promise.resolve({
        simulated: true,
        execution_permitted: false,
        order_submitted: false,
        orders: [],
      });
    });
    renderPage();

    expect(await screen.findByText("No simulated balances yet. The paper-swap CLI records them.")).toBeInTheDocument();
    expect(screen.getByText("No simulated swaps yet.")).toBeInTheDocument();
    expect(screen.getByText("Simulated")).toBeInTheDocument();
  });

  it("shows an error when the ledger cannot be read", async () => {
    vi.mocked(apiGet).mockRejectedValue(new Error("down"));
    renderPage();

    expect(await screen.findAllByText("The paper-swap ledger is unavailable.")).toHaveLength(2);
    expect(screen.queryByText("0.9899")).not.toBeInTheDocument();
  });
});
