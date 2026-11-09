import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiGet } from "../api/client";
import type { TreasuryMonthlySummary } from "../api/types";
import { AppRoutes } from "../App";

vi.mock("../api/client", () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
}));

const summary: TreasuryMonthlySummary = {
  period: "2026-11",
  period_closed: false,
  realised_profit: "10.00",
  costs: "0.00",
  loss_carryforward: "0.00",
  eligible_profit: "10.00",
  proposed_distribution: "5.00",
  retained: "5.00",
  loss_carryforward_out: "0.00",
  distribution_fraction: "0.50",
  distribution_cap: "2000.00",
  review_day: 5,
  review_on: "2026-12-07",
  review_shifted_for_weekend: true,
  fills_counted: 2,
  fees_included: false,
  carryforward_stored: false,
  broker_reconciled: false,
  settled: false,
  transfer_status: "not_attempted",
  approval_route: "absent",
  execution_permitted: false,
  order_submitted: false,
  transfer_submitted: false,
  source: "local_projection",
  note: "Local projection. This is not a broker balance and not a transfer.",
};

function renderTreasury() {
  render(
    <MemoryRouter initialEntries={["/treasury"]}>
      <AppRoutes />
    </MemoryRouter>,
  );
}

describe("treasury page", () => {
  beforeEach(() => {
    vi.mocked(apiGet).mockReset();
  });

  it("shows a local projection and has no payout control", async () => {
    vi.mocked(apiGet).mockResolvedValue(summary);
    renderTreasury();

    expect(await screen.findByRole("heading", { name: "Treasury" })).toBeInTheDocument();
    expect(screen.getByText("10.00")).toBeInTheDocument();
    expect(screen.getAllByText("5.00")).toHaveLength(2);
    expect(screen.getByText("2026-12-07")).toBeInTheDocument();
    expect(screen.getAllByText(/not a transfer/i).length).toBeGreaterThan(0);
    expect(
      screen.queryByRole("button", { name: /approve|transfer|submit|payout/i }),
    ).not.toBeInTheDocument();
    expect(vi.mocked(apiGet)).toHaveBeenCalledWith("/api/v1/treasury/monthly-summary");
  });

  it("does not invent a payout when the summary is unavailable", async () => {
    vi.mocked(apiGet).mockRejectedValue(new Error("down"));
    renderTreasury();

    expect(
      await screen.findByText("Treasury summary is unavailable. No payout was invented."),
    ).toBeInTheDocument();
    expect(screen.queryByText("5.00")).not.toBeInTheDocument();
  });

  it("hides a summary that claims a transfer was submitted", async () => {
    vi.mocked(apiGet).mockResolvedValue({
      ...summary,
      transfer_submitted: true,
    } as unknown as TreasuryMonthlySummary);
    renderTreasury();

    expect(
      await screen.findByText("Treasury summary is unavailable. No payout was invented."),
    ).toBeInTheDocument();
    expect(screen.queryByText("5.00")).not.toBeInTheDocument();
  });
});
