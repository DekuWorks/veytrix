import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiGet } from "../api/client";
import type { ReconciliationResponse } from "../api/types";
import { AppRoutes } from "../App";

vi.mock("../api/client", () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
}));

const view: ReconciliationResponse = {
  local_orders: 1,
  local_fills: 1,
  local_open: 0,
  broker_rows_read: 0,
  broker_read: "absent",
  alpaca_called: false,
  reconciled: false,
  rows: [
    {
      client_order_id: "mac01-paper-2",
      mode: "paper",
      side: "buy",
      local_status: "filled",
      broker_order_id: "broker-id-2",
      broker_order_stored: true,
      broker_status: "not_read",
      matched: false,
      reason: "broker_not_read",
    },
  ],
  execution_permitted: false,
  order_submitted: false,
  order_route: "absent",
  source: "local_ledger",
  note: "These rows are the local MAC-01 ledger.",
};

function renderPage() {
  render(
    <MemoryRouter initialEntries={["/reconciliation"]}>
      <AppRoutes />
    </MemoryRouter>,
  );
}

describe("reconciliation page", () => {
  beforeEach(() => {
    vi.mocked(apiGet).mockReset();
  });

  it("shows a local fill that is not a broker match", async () => {
    vi.mocked(apiGet).mockResolvedValue(view);
    renderPage();

    expect(await screen.findByRole("heading", { name: "Reconciliation" })).toBeInTheDocument();
    expect(screen.getByText("absent")).toBeInTheDocument();
    expect(screen.getByText("mac01-paper-2")).toBeInTheDocument();
    expect(screen.getByText("not_read")).toBeInTheDocument();
    expect(screen.getByText("filled")).toBeInTheDocument();
    expect(screen.queryByText("broker-id-2")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Reconciliation" })).toHaveAttribute(
      "href",
      "/reconciliation",
    );
    expect(screen.queryByRole("button", { name: /submit|reconcile|refresh broker/i })).not.toBeInTheDocument();
    expect(vi.mocked(apiGet)).toHaveBeenCalledWith("/api/v1/ledger/reconciliation");
  });

  it("does not invent orders when the read fails", async () => {
    vi.mocked(apiGet).mockRejectedValue(new Error("down"));
    renderPage();

    expect(
      await screen.findByText("Reconciliation is unavailable. No broker balance was invented."),
    ).toBeInTheDocument();
    expect(screen.queryByText("mac01-paper-2")).not.toBeInTheDocument();
  });

  it("hides a payload that says the book is reconciled", async () => {
    vi.mocked(apiGet).mockResolvedValue({ ...view, reconciled: true });
    renderPage();

    expect(
      await screen.findByText("Reconciliation is unavailable. No broker balance was invented."),
    ).toBeInTheDocument();
    expect(screen.queryByText("mac01-paper-2")).not.toBeInTheDocument();
  });
});
