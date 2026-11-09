import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiGet } from "../api/client";
import type { Mac01ScheduleResponse } from "../api/types";
import { AppRoutes } from "../App";

vi.mock("../api/client", () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
}));

const schedule: Mac01ScheduleResponse = {
  strategy: "mac-01",
  timezone: "America/New_York",
  run_clock: "09:35",
  delay_after_open_minutes: 5,
  calendar: "not_read",
  next_session: "unknown",
  running: false,
  process: "absent",
  submit_flag: false,
  can_start: false,
  config_valid: true,
  config_mode: "paper",
  config_submit_orders: false,
  config_live_enabled: false,
  alpaca_called: false,
  execution_permitted: false,
  order_submitted: false,
  order_route: "absent",
  source: "local_config",
  note: "The API does not start the scheduler and does not read the Alpaca calendar.",
};

function renderPage() {
  render(
    <MemoryRouter initialEntries={["/scheduler"]}>
      <AppRoutes />
    </MemoryRouter>,
  );
}

describe("scheduler page", () => {
  beforeEach(() => {
    vi.mocked(apiGet).mockReset();
  });

  it("shows a stopped clock and no start control", async () => {
    vi.mocked(apiGet).mockResolvedValue(schedule);
    renderPage();

    expect(await screen.findByRole("heading", { name: "Scheduler" })).toBeInTheDocument();
    expect(screen.getByText("09:35 America/New_York")).toBeInTheDocument();
    expect(screen.getByText("not_read")).toBeInTheDocument();
    expect(screen.getByText("unknown")).toBeInTheDocument();
    expect(screen.getByText("absent")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Scheduler" })).toHaveAttribute("href", "/scheduler");
    expect(screen.queryByRole("button", { name: /start|submit|schedule/i })).not.toBeInTheDocument();
    expect(vi.mocked(apiGet)).toHaveBeenCalledWith("/api/v1/strategies/mac-01/schedule");
  });

  it("does not invent a running process when the read fails", async () => {
    vi.mocked(apiGet).mockRejectedValue(new Error("down"));
    renderPage();

    expect(
      await screen.findByText("Scheduler status is unavailable. No run was started."),
    ).toBeInTheDocument();
    expect(screen.queryByText("09:35 America/New_York")).not.toBeInTheDocument();
  });

  it("hides a payload that says the scheduler can start", async () => {
    vi.mocked(apiGet).mockResolvedValue({ ...schedule, can_start: true });
    renderPage();

    expect(
      await screen.findByText("Scheduler status is unavailable. No run was started."),
    ).toBeInTheDocument();
    expect(screen.queryByText("09:35 America/New_York")).not.toBeInTheDocument();
  });
});
