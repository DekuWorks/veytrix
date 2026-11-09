import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiGet } from "../api/client";
import type { SubmissionEvidenceResponse } from "../api/types";
import { AppRoutes } from "../App";

vi.mock("../api/client", () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
}));

const NAMES = [
  "mode_live",
  "live_enabled",
  "submit_orders",
  "confirm_phrase",
  "submit_flag",
  "account_match",
  "account_active",
  "kill_switch_off",
] as const;

const evidence: SubmissionEvidenceResponse = {
  config_valid: true,
  config_mode: "paper",
  config_live_enabled: false,
  config_submit_orders: false,
  config_kill_switch: false,
  expected_account_set: false,
  conditions: NAMES.map((name) => ({ name, met: false })),
  conditions_met: 0,
  account_status: "not_read",
  ledger_kill_switch: "not_read",
  submit_flag: false,
  api_reaches_engine: false,
  broker_called: false,
  paper_submission_from_api: false,
  live_submission_possible: false,
  expected_account_echoed: false,
  confirm_phrase_echoed: false,
  execution_permitted: false,
  order_submitted: false,
  order_route: "absent",
  source: "local_config",
  note: "This process cannot pass --submit.",
};

function renderPage() {
  render(
    <MemoryRouter initialEntries={["/live-gate"]}>
      <AppRoutes />
    </MemoryRouter>,
  );
}

describe("live gate page", () => {
  beforeEach(() => {
    vi.mocked(apiGet).mockReset();
  });

  it("shows eight unmet conditions and no switch", async () => {
    vi.mocked(apiGet).mockResolvedValue(evidence);
    renderPage();

    expect(await screen.findByRole("heading", { name: "Live gate" })).toBeInTheDocument();
    expect(screen.getByText("mode_live")).toBeInTheDocument();
    expect(screen.getByText("kill_switch_off")).toBeInTheDocument();
    expect(screen.getAllByText("not_read").length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "Live gate" })).toHaveAttribute("href", "/live-gate");
    expect(screen.queryByRole("switch")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /submit|enable|live/i })).not.toBeInTheDocument();
    expect(vi.mocked(apiGet)).toHaveBeenCalledWith("/api/v1/system/submission");
  });

  it("does not invent a submission when the read fails", async () => {
    vi.mocked(apiGet).mockRejectedValue(new Error("down"));
    renderPage();

    expect(
      await screen.findByText("Live-gate evidence is unavailable. Nothing was submitted."),
    ).toBeInTheDocument();
    expect(screen.queryByText("mode_live")).not.toBeInTheDocument();
  });

  it("hides a payload that says live submission is possible", async () => {
    vi.mocked(apiGet).mockResolvedValue({ ...evidence, live_submission_possible: true });
    renderPage();

    expect(
      await screen.findByText("Live-gate evidence is unavailable. Nothing was submitted."),
    ).toBeInTheDocument();
    expect(screen.queryByText("mode_live")).not.toBeInTheDocument();
  });
});
