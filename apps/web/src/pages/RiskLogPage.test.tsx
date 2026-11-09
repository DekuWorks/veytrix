import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiGet } from "../api/client";
import type { RiskEventLogResponse } from "../api/types";
import { AppRoutes } from "../App";

vi.mock("../api/client", () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
}));

const log: RiskEventLogResponse = {
  events: [
    {
      id: "11111111-1111-1111-1111-111111111111",
      created_at: "2026-11-08T16:00:00Z",
      correlation_id: "risk-log-1",
      action: "risk.size.recorded",
      symbol: "BTC-USD",
      shares: 1,
      binding_constraint: "risk",
      execution_permitted: false,
      order_submitted: false,
    },
  ],
  unlogged: [
    { kind: "shield_preview", persisted: false },
    { kind: "reservation_preview", persisted: false },
  ],
  persisted_action: "risk.size.recorded",
  shield_persisted: false,
  reservation_persisted: false,
  execution_permitted: false,
  order_submitted: false,
  source: "local_audit_log",
  note: "Only a stored size is listed.",
};

function renderPage() {
  render(
    <MemoryRouter initialEntries={["/risk-log"]}>
      <AppRoutes />
    </MemoryRouter>,
  );
}

describe("risk log page", () => {
  beforeEach(() => {
    vi.mocked(apiGet).mockReset();
  });

  it("shows an unstored preview and a size that did not submit", async () => {
    vi.mocked(apiGet).mockResolvedValue(log);
    renderPage();

    expect(await screen.findByRole("heading", { name: "Risk log" })).toBeInTheDocument();
    expect(screen.getByText("shield_preview")).toBeInTheDocument();
    expect(screen.getByText("reservation_preview")).toBeInTheDocument();
    expect(screen.getByText("BTC-USD")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Risk log" })).toHaveAttribute("href", "/risk-log");
    expect(screen.queryByRole("button", { name: /submit|approve|record/i })).not.toBeInTheDocument();
    expect(vi.mocked(apiGet)).toHaveBeenCalledWith("/api/v1/risk/log");
  });

  it("does not invent events when the read fails", async () => {
    vi.mocked(apiGet).mockRejectedValue(new Error("down"));
    renderPage();

    expect(
      await screen.findByText("The risk event log is unavailable. No order was recorded."),
    ).toBeInTheDocument();
    expect(screen.queryByText("BTC-USD")).not.toBeInTheDocument();
  });

  it("hides a log that says a preview was stored", async () => {
    vi.mocked(apiGet).mockResolvedValue({
      ...log,
      unlogged: [
        { kind: "shield_preview", persisted: true },
        { kind: "reservation_preview", persisted: false },
      ],
    });
    renderPage();

    expect(
      await screen.findByText("The risk event log is unavailable. No order was recorded."),
    ).toBeInTheDocument();
    expect(screen.queryByText("BTC-USD")).not.toBeInTheDocument();
  });
});
