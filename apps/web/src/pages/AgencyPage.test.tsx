import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiGet, apiPost } from "../api/client";
import { AGENT_CODES, DENIED_TOOLS, type AgentDesk, type DeskDetail } from "../api/types";
import { AppRoutes } from "../App";
import { AGENCY_NOTICE } from "../content";

vi.mock("../api/client", () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiDelete: vi.fn(),
}));

function desk(code: (typeof AGENT_CODES)[number], name: string): AgentDesk {
  return {
    code,
    display_name: name,
    desk: "desk",
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
  desk("CRYPTO-01", "Crypto desk"),
  desk("DAY-01", "Day desk"),
  desk("DEFI-01", "DeFi desk"),
  desk("ETF-01", "ETF desk"),
  desk("RESEARCH-01", "Research desk"),
  desk("RISK-01", "Risk desk"),
  desk("STOCK-01", "Stock desk"),
  desk("SUPERVISOR-01", "Supervisor"),
  desk("TREASURY-01", "Treasury desk"),
];

function detail(code: (typeof AGENT_CODES)[number] = "SUPERVISOR-01"): DeskDetail {
  return {
    ...desk(code, "Supervisor"),
    notes: "Registry row only. This desk is not running.",
    tools: DENIED_TOOLS.map((tool_name) => ({ tool_name, effect: "deny" as const })),
    running: false,
    can_enable: false,
    source: "local_registry",
    trading_rights: "denied",
    execution_permitted: false,
    order_submitted: false,
  };
}

function renderPage(path = "/agency") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppRoutes />
    </MemoryRouter>,
  );
}

describe("agency page", () => {
  beforeEach(() => {
    vi.mocked(apiGet).mockReset();
    vi.mocked(apiPost).mockReset();
  });

  it("lists disabled desks and has no enable or order control", async () => {
    vi.mocked(apiGet).mockResolvedValue({
      agents,
      source: "local_registry",
      trading_rights: "denied",
      execution_permitted: false,
      order_submitted: false,
    });
    renderPage();

    expect(await screen.findByRole("heading", { name: "Agency" })).toBeInTheDocument();
    expect(screen.getByText(AGENCY_NOTICE)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Agency" })).toHaveAttribute("href", "/agency");
    expect(screen.getByRole("link", { name: "SUPERVISOR-01" })).toHaveAttribute(
      "href",
      "/agency/SUPERVISOR-01",
    );
    expect(screen.getByText("TREASURY-01")).toBeInTheDocument();
    expect(screen.getAllByText("disabled")).toHaveLength(9);
    expect(screen.getAllByText("Denied").length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: /enable|submit|trade|order/i })).not.toBeInTheDocument();
    expect(vi.mocked(apiGet)).toHaveBeenCalledWith("/api/v1/agents");
    expect(vi.mocked(apiPost)).not.toHaveBeenCalled();
  });

  it("does not invent desks when the registry is unavailable", async () => {
    vi.mocked(apiGet).mockRejectedValue(new Error("down"));
    renderPage();

    expect(
      await screen.findByText("The agent registry is unavailable. No desk was invented."),
    ).toBeInTheDocument();
    expect(screen.queryByText("SUPERVISOR-01")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /enable|submit|trade|order/i })).not.toBeInTheDocument();
  });

  it("hides a payload that grants trading rights", async () => {
    vi.mocked(apiGet).mockResolvedValue({
      agents: agents.map((agent) =>
        agent.code === "STOCK-01" ? { ...agent, can_submit_orders: true } : agent,
      ),
      source: "local_registry",
      trading_rights: "denied",
      execution_permitted: false,
      order_submitted: false,
    });
    renderPage();

    expect(
      await screen.findByText("The agent registry is unavailable. No desk was invented."),
    ).toBeInTheDocument();
    expect(screen.queryByText("STOCK-01")).not.toBeInTheDocument();
  });

  it("shows a desk and its deny list without an enable control", async () => {
    vi.mocked(apiGet).mockResolvedValue(detail());
    renderPage("/agency/SUPERVISOR-01");

    expect(await screen.findByRole("heading", { name: "SUPERVISOR-01" })).toBeInTheDocument();
    expect(screen.getByText("Registry row only. This desk is not running.")).toBeInTheDocument();
    expect(screen.getByText("submit_order")).toBeInTheDocument();
    expect(screen.getByText("bank_transfer")).toBeInTheDocument();
    expect(screen.getAllByText("Deny")).toHaveLength(DENIED_TOOLS.length);
    expect(screen.getByRole("link", { name: "All desks" })).toHaveAttribute("href", "/agency");
    expect(screen.queryByRole("button", { name: /enable|submit|trade|order/i })).not.toBeInTheDocument();
    expect(vi.mocked(apiGet)).toHaveBeenCalledWith("/api/v1/agency/desks/SUPERVISOR-01");
    expect(vi.mocked(apiPost)).not.toHaveBeenCalled();
  });

  it("does not invent a desk for an unknown code", async () => {
    renderPage("/agency/NOPE");

    expect(
      await screen.findByText("That desk is not in the registry. Nothing was enabled."),
    ).toBeInTheDocument();
    expect(screen.queryByText("NOPE")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /enable|submit|trade|order/i })).not.toBeInTheDocument();
    expect(vi.mocked(apiGet)).not.toHaveBeenCalled();
  });

  it("hides a desk detail that could trade", async () => {
    vi.mocked(apiGet).mockResolvedValue({ ...detail("STOCK-01"), can_submit_orders: true });
    renderPage("/agency/STOCK-01");

    expect(
      await screen.findByText("This desk cannot be shown. Nothing was enabled."),
    ).toBeInTheDocument();
    expect(screen.queryByText("STOCK-01")).not.toBeInTheDocument();
    expect(screen.queryByText("submit_order")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /enable|submit|trade|order/i })).not.toBeInTheDocument();
  });
});
