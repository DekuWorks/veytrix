import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiGet } from "../api/client";
import type { FuturesPostureResponse } from "../api/types";
import { AppRoutes } from "../App";

vi.mock("../api/client", () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiDelete: vi.fn(),
}));

const posture: FuturesPostureResponse = {
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
  note: "FUTURES-01 is disabled. This API does not submit an order.",
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/futures"]}>
      <AppRoutes />
    </MemoryRouter>,
  );
}

describe("futures page", () => {
  beforeEach(() => {
    vi.mocked(apiGet).mockReset();
  });

  it("shows a disabled desk and has no order control", async () => {
    vi.mocked(apiGet).mockResolvedValue(posture);
    renderPage();

    expect(await screen.findByRole("heading", { name: "Futures · FUTURES-01" })).toBeInTheDocument();
    expect(screen.getByText("MES, MNQ")).toBeInTheDocument();
    expect(screen.getAllByText("disabled").length).toBeGreaterThan(0);
    expect(screen.getByText("not_connected")).toBeInTheDocument();
    expect(screen.getByText("absent")).toBeInTheDocument();
    expect(screen.getAllByText("false").length).toBeGreaterThanOrEqual(3);
    expect(screen.getByText(/No order is sent/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /enable|submit|trade|order/i })).not.toBeInTheDocument();
    expect(vi.mocked(apiGet)).toHaveBeenCalledWith("/api/v1/futures/posture");
  });

  it("hides a payload that says the desk can trade", async () => {
    vi.mocked(apiGet).mockResolvedValue({ ...posture, execution_permitted: true, can_enable: true });
    renderPage();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Futures posture is unavailable. No order was sent.",
    );
    expect(screen.queryByText("MES, MNQ")).not.toBeInTheDocument();
  });

  it("does not invent a desk when the read fails", async () => {
    vi.mocked(apiGet).mockRejectedValue(new Error("down"));
    renderPage();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Futures posture is unavailable. No order was sent.",
    );
    expect(screen.queryByText("MES, MNQ")).not.toBeInTheDocument();
  });
});
