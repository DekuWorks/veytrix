import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiGet } from "../api/client";
import type { DiagnosticsResponse } from "../api/types";
import { AppRoutes } from "../App";

vi.mock("../api/client", () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
}));

const diagnostics: DiagnosticsResponse = {
  service: "veytrix-api",
  env: "local",
  trading_mode: "paper",
  live_broker: "disabled",
  auth: "not_configured",
  sample_data: true,
  execution_permitted: false,
  daily_weekly_stops_enforced: false,
  rate_limit: "process_local",
  csrf: "not_implemented",
  versions: { api: "0.1.0", python: "3.14.6" },
};

function renderSettings() {
  render(
    <MemoryRouter initialEntries={["/settings"]}>
      <AppRoutes />
    </MemoryRouter>,
  );
}

describe("settings page", () => {
  beforeEach(() => {
    vi.mocked(apiGet).mockReset();
  });

  it("shows the fixed posture and has no editor", async () => {
    vi.mocked(apiGet).mockResolvedValue(diagnostics);
    renderSettings();

    expect(await screen.findByRole("heading", { name: "Settings" })).toBeInTheDocument();
    expect(screen.getByText("not_configured")).toBeInTheDocument();
    expect(screen.getByText("not_implemented")).toBeInTheDocument();
    expect(screen.getByText("process_local")).toBeInTheDocument();
    expect(screen.getByText("disabled")).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(screen.queryByRole("switch")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /save|enable|live|submit/i }),
    ).not.toBeInTheDocument();
    expect(vi.mocked(apiGet)).toHaveBeenCalledWith("/api/v1/diagnostics");
  });

  it("does not invent a live switch when diagnostics fail", async () => {
    vi.mocked(apiGet).mockRejectedValue(new Error("down"));
    renderSettings();

    expect(
      await screen.findByText("Settings are unavailable. No live switch was invented."),
    ).toBeInTheDocument();
    expect(screen.queryByText("not_configured")).not.toBeInTheDocument();
  });

  it("hides a payload that says execution is permitted", async () => {
    vi.mocked(apiGet).mockResolvedValue({
      ...diagnostics,
      execution_permitted: true,
    } as unknown as DiagnosticsResponse);
    renderSettings();

    expect(
      await screen.findByText("Settings are unavailable. No live switch was invented."),
    ).toBeInTheDocument();
    expect(screen.queryByText("not_configured")).not.toBeInTheDocument();
  });
});
