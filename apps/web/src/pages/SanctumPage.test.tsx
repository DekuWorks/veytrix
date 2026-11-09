import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiGet } from "../api/client";
import { AGENT_CODES, DENIED_TOOLS, type AgentCode, type AgentDesk } from "../api/types";
import { AppRoutes } from "../App";

vi.mock("../api/client", () => ({
  apiGet: vi.fn(),
}));

vi.mock("../sanctum/game", () => ({
  createSanctumGame: () => ({
    destroy: () => undefined,
    setMode: () => undefined,
    panBy: () => undefined,
    zoomBy: () => undefined,
    fit: () => undefined,
    follow: () => undefined,
    setPoses: () => undefined,
    gather: () => undefined,
    returnToDesks: () => undefined,
  }),
}));

function desk(code: AgentCode, displayName: string, name: string): AgentDesk {
  return {
    code,
    display_name: displayName,
    desk: name,
    status: "disabled",
    paper_only: true,
    can_submit_orders: false,
    can_sign: false,
    can_transfer_funds: false,
    holds_credentials: false,
    permission_effect: "deny",
  };
}

const agents = [
  desk("SUPERVISOR-01", "Supervisor", "supervision"),
  desk("DAY-01", "Day desk", "equities-session"),
  desk("STOCK-01", "Stock desk", "equities-swing"),
  desk("CRYPTO-01", "Crypto desk", "crypto-display"),
  desk("ETF-01", "ETF desk", "etf"),
  desk("DEFI-01", "DeFi desk", "simulated-swap"),
  desk("RESEARCH-01", "Research desk", "research"),
  desk("RISK-01", "Risk desk", "risk"),
  desk("TREASURY-01", "Treasury desk", "treasury"),
  desk("FUTURES-01", "Futures desk", "futures-research"),
];

describe("sanctum route", () => {
  beforeEach(() => {
    vi.mocked(apiGet).mockReset();
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path === "/api/v1/agents") {
        return Promise.resolve({
          agents,
          source: "local_registry",
          trading_rights: "denied",
          execution_permitted: false,
          order_submitted: false,
        });
      }
      if (path === "/api/v1/futures/posture") {
        return Promise.resolve({
          desk: "FUTURES-01",
          status: "disabled",
          symbols: ["MES", "MNQ"],
          topstep_automation: "disabled",
          topstep_account: "not_connected",
          orders: "absent",
          market_data: "not_read",
          can_enable: false,
          execution_permitted: false,
          order_submitted: false,
          broker_called: false,
          source: "local_posture",
          note: "FUTURES-01 is disabled. Topstep automation is off. This API does not submit an order.",
        });
      }
      if (path === "/api/v1/audit/log") {
        return Promise.resolve({
          events: [],
          source: "local_audit_log",
          execution_permitted: false,
          order_submitted: false,
        });
      }
      if (path === "/api/v1/ledger/reconciliation") {
        return Promise.resolve({
          local_orders: 0,
          broker_read: "absent",
          reconciled: false,
          rows: [],
        });
      }
      if (path === "/api/v1/health") {
        return Promise.resolve({ status: "ok" });
      }
      if (path === "/api/v1/diagnostics") {
        return Promise.resolve({
          live_broker: "disabled",
          trading_mode: "paper",
          execution_permitted: false,
        });
      }
      if (path.startsWith("/api/v1/treasury/reminders")) {
        return Promise.resolve({
          accounting_close_on: "2026-12-01",
          payout_review_on: "2026-12-07",
          meeting_time: "unconfirmed",
          daypilot: "absent",
          event_created: false,
        });
      }
      if (path.startsWith("/api/v1/agency/desks/")) {
        return Promise.resolve({
          ...desk("SUPERVISOR-01", "Supervisor", "supervision"),
          notes: "Registry row only. This desk is not running. It cannot submit an order.",
          tools: DENIED_TOOLS.map((tool) => ({ tool_name: tool, effect: "deny" as const })),
          running: false,
          can_enable: false,
          source: "local_registry",
          trading_rights: "denied",
          execution_permitted: false,
          order_submitted: false,
        });
      }
      return Promise.reject(new Error(path));
    });
  });

  it("renders the sky view, the ten desks, the boardroom, and no trading control", async () => {
    render(
      <MemoryRouter initialEntries={["/sanctum"]}>
        <AppRoutes />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Sanctum — Sky View" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sanctum" })).toHaveAttribute("href", "/sanctum");
    for (const code of AGENT_CODES) {
      expect(screen.getAllByText(code).length).toBeGreaterThan(0);
    }
    expect(screen.getByText("BOARDROOM")).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Trading" })).toHaveAttribute(
      "title",
      "Frame the trading desks. No order is sent.",
    );
    expect(screen.queryByRole("button", { name: /order|enable|sign|withdraw|topstep/i })).not.toBeInTheDocument();
    expect(screen.getAllByText("Paper").length).toBeGreaterThan(0);
    expect(screen.getByText("Simulation (Paper)")).toBeInTheDocument();
    expect(screen.getByText("Dayvid · DAY-01: Scanning intraday setups")).toBeInTheDocument();
    expect(screen.getByText("Astra · RESEARCH-01: Compiling market intel")).toBeInTheDocument();
    expect(screen.getByText("Futures · FUTURES-01: Reviewing Topstep rules")).toBeInTheDocument();
    expect(screen.getByText("Aegis · RISK-01: Monitoring exposure limits")).toBeInTheDocument();
    expect(screen.getByText("Midas · TREASURY-01: Reconciling balances")).toBeInTheDocument();
    for (const name of ["Roads", "Dayvid", "Vex", "Nyx", "Cipher", "Lyra", "Astra", "Aegis", "Midas", "Futures"]) {
      expect(screen.getAllByText(name).length).toBeGreaterThan(0);
    }
    expect(screen.getAllByText(/No order is sent/).length).toBeGreaterThan(0);
  });
});
