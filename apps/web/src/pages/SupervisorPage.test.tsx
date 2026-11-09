import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiGet } from "../api/client";
import type { SupervisorToolsResponse } from "../api/types";
import { AppRoutes } from "../App";

vi.mock("../api/client", () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
}));

const READ_TOOLS = [
  "read_system_status",
  "read_agents",
  "read_desk",
  "read_market_health",
  "read_treasury_summary",
  "read_audit_log",
  "read_research_notes",
] as const;

const DENY_TOOLS = [
  "submit_order",
  "cancel_order",
  "sign_transaction",
  "broadcast_transaction",
  "bank_transfer",
  "set_live_mode",
  "release_kill_switch",
  "enable_agent",
  "approve_payout",
  "size_position",
  "supervisor_chat",
] as const;

const catalogue: SupervisorToolsResponse = {
  source: "local_catalogue",
  model: "not_configured",
  chat: "absent",
  executed: false,
  invokes_model: false,
  execution_permitted: false,
  order_submitted: false,
  note: "Local tool catalogue.",
  tools: [...READ_TOOLS, ...DENY_TOOLS].map((name, index) => ({
    name,
    effect: index < READ_TOOLS.length ? "read" : "deny",
    executes: false,
  })),
};

function renderSupervisor() {
  render(
    <MemoryRouter initialEntries={["/supervisor"]}>
      <AppRoutes />
    </MemoryRouter>,
  );
}

describe("supervisor page", () => {
  beforeEach(() => {
    vi.mocked(apiGet).mockReset();
  });

  it("lists the catalogue and has no chat box", async () => {
    vi.mocked(apiGet).mockResolvedValue(catalogue);
    renderSupervisor();

    expect(await screen.findByRole("heading", { name: "Supervisor" })).toBeInTheDocument();
    expect(screen.getByText("not_configured")).toBeInTheDocument();
    expect(screen.getByText("absent")).toBeInTheDocument();
    expect(screen.getByText("read_system_status")).toBeInTheDocument();
    expect(screen.getByText("submit_order")).toBeInTheDocument();
    expect(screen.getByText("size_position")).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(screen.queryByRole("switch")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /send|run|enable|submit|chat/i })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Supervisor" })).toHaveAttribute("href", "/supervisor");
    expect(vi.mocked(apiGet)).toHaveBeenCalledWith("/api/v1/supervisor/tools");
  });

  it("does not invent a chat box when the catalogue fails", async () => {
    vi.mocked(apiGet).mockRejectedValue(new Error("down"));
    renderSupervisor();

    expect(
      await screen.findByText("Supervisor tools are unavailable. No chat box was invented."),
    ).toBeInTheDocument();
    expect(screen.queryByText("read_system_status")).not.toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("hides a payload that says a tool executes", async () => {
    vi.mocked(apiGet).mockResolvedValue({
      ...catalogue,
      tools: catalogue.tools.map((tool) =>
        tool.name === "submit_order" ? { ...tool, executes: true } : tool,
      ),
    } as unknown as SupervisorToolsResponse);
    renderSupervisor();

    expect(
      await screen.findByText("Supervisor tools are unavailable. No chat box was invented."),
    ).toBeInTheDocument();
    expect(screen.queryByText("submit_order")).not.toBeInTheDocument();
  });
});
