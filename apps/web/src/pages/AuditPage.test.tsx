import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiGet, apiPost } from "../api/client";
import type { AuditLogEntry, DiagnosticsResponse, PaperSizeJournalEntry } from "../api/types";
import { AppRoutes } from "../App";
import { LIVE_NOTICE, SAMPLE_DISCLAIMER } from "../content";

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
  versions: { api: "0.1.0", python: "3.14" },
};

const journalEntry: PaperSizeJournalEntry = {
  id: "size-1",
  recorded_at: "2026-11-08T04:40:00Z",
  symbol: "ETH-USD",
  equity: "100000.00",
  entry: "2233.58",
  stop: "2200.00",
  shares: 4,
  planned_risk: "134.32",
  binding_constraint: "allocation",
  execution_permitted: false,
  order_submitted: false,
};

function renderAudit() {
  render(
    <MemoryRouter initialEntries={["/audit"]}>
      <AppRoutes />
    </MemoryRouter>,
  );
}

const emptyLog = {
  events: [] as AuditLogEntry[],
  source: "local_audit_log" as const,
  execution_permitted: false as const,
  order_submitted: false as const,
};

const auditEntry: AuditLogEntry = {
  id: "audit-1",
  created_at: "2026-11-08T04:41:00Z",
  correlation_id: "size-audit-1",
  action: "risk.size.recorded",
  symbol: "BTC-USD",
  shares: 2,
  binding_constraint: "risk",
  execution_permitted: false,
  order_submitted: false,
};

function mockAudit(entries: PaperSizeJournalEntry[] = [], events: AuditLogEntry[] = []) {
  vi.mocked(apiGet).mockImplementation((path: string) => {
    if (path.includes("size-journal")) {
      return Promise.resolve({ entries });
    }
    if (path.includes("/audit/log")) {
      return Promise.resolve({ ...emptyLog, events });
    }
    return Promise.resolve(diagnostics);
  });
}

describe("audit page", () => {
  beforeEach(() => {
    vi.mocked(apiGet).mockReset();
    vi.mocked(apiPost).mockReset();
    mockAudit();
  });

  it("shows the diagnostics fields from the API", async () => {
    renderAudit();

    expect(await screen.findByText("local")).toBeInTheDocument();
    expect(screen.getByText("paper")).toBeInTheDocument();
    expect(screen.getByText("disabled")).toBeInTheDocument();
    expect(screen.getByText("not_configured")).toBeInTheDocument();
    expect(screen.getAllByText("false").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("Sample series present")).toBeInTheDocument();
    expect(screen.queryByText("Sample series absent")).not.toBeInTheDocument();
    expect(screen.getAllByText(LIVE_NOTICE).length).toBeGreaterThan(0);
    expect(screen.getByText(SAMPLE_DISCLAIMER)).toBeInTheDocument();
    expect(screen.getAllByText(/No order is sent/).length).toBeGreaterThan(0);
    expect(screen.getByText("No paper sizes recorded yet.")).toBeInTheDocument();
    expect(screen.getByText("No audit events recorded yet.")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        name: "Paper size journal on this machine. Not an order. The stop is not enforced. No order is sent.",
      }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Execution permitted true")).not.toBeInTheDocument();
    expect(vi.mocked(apiGet)).toHaveBeenCalledWith("/api/v1/diagnostics");
    expect(vi.mocked(apiGet)).toHaveBeenCalledWith("/api/v1/audit/size-journal");
    expect(vi.mocked(apiGet)).toHaveBeenCalledWith("/api/v1/audit/log");
    expect(vi.mocked(apiGet)).not.toHaveBeenCalledWith("/api/v1/risk/size");
    expect(vi.mocked(apiPost)).not.toHaveBeenCalled();
  });

  it("does not invent a status when the probe fails", async () => {
    vi.mocked(apiGet).mockRejectedValue(new Error("down"));
    renderAudit();

    expect(await screen.findByText("Diagnostics probe failed. No status was invented.")).toBeInTheDocument();
    expect(screen.getByText("Paper size journal is unavailable. No size was invented.")).toBeInTheDocument();
    expect(screen.getByText("Audit log is unavailable. No event was invented.")).toBeInTheDocument();
    expect(screen.queryByText("No paper sizes recorded yet.")).not.toBeInTheDocument();
    expect(screen.queryByText("No audit events recorded yet.")).not.toBeInTheDocument();
    expect(screen.queryByText("paper")).not.toBeInTheDocument();
    expect(screen.queryByText("local")).not.toBeInTheDocument();
    expect(screen.queryByText("healthy")).not.toBeInTheDocument();
    expect(screen.queryByText("Sample series present")).not.toBeInTheDocument();
    expect(screen.queryByText("Sample series absent")).not.toBeInTheDocument();
    expect(screen.queryByRole("definition")).not.toBeInTheDocument();
    expect(screen.getAllByText(LIVE_NOTICE).length).toBeGreaterThan(0);
    expect(screen.getByText(SAMPLE_DISCLAIMER)).toBeInTheDocument();
    expect(vi.mocked(apiPost)).not.toHaveBeenCalled();
  });

  it("shows an empty journal when diagnostics fail on their own", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.includes("size-journal")) {
        return Promise.resolve({ entries: [] });
      }
      return Promise.reject(new Error("down"));
    });
    renderAudit();

    expect(await screen.findByText("Diagnostics probe failed. No status was invented.")).toBeInTheDocument();
    expect(screen.getByText("No paper sizes recorded yet.")).toBeInTheDocument();
    expect(screen.queryByText("paper")).not.toBeInTheDocument();
    expect(screen.queryByText("Paper size journal is unavailable. No size was invented.")).not.toBeInTheDocument();
    expect(vi.mocked(apiPost)).not.toHaveBeenCalled();
  });

  it("shows a fixture journal row and does not call the size route", async () => {
    mockAudit([journalEntry]);
    renderAudit();

    expect(await screen.findByRole("heading", { name: "ETH-USD" })).toBeInTheDocument();
    expect(screen.getByText("Shares 4")).toBeInTheDocument();
    expect(screen.getByText("Binding constraint allocation")).toBeInTheDocument();
    expect(screen.getByText("Planned risk 134.32")).toBeInTheDocument();
    expect(screen.getByText("Recorded at 2026-11-08T04:40:00Z.")).toBeInTheDocument();
    expect(screen.getByText("local")).toBeInTheDocument();
    expect(screen.queryByText("No paper sizes recorded yet.")).not.toBeInTheDocument();
    expect(screen.queryByText(/order id/i)).not.toBeInTheDocument();
    expect(screen.queryByText("order-1")).not.toBeInTheDocument();
    expect(vi.mocked(apiGet)).toHaveBeenCalledWith("/api/v1/audit/size-journal");
    expect(vi.mocked(apiGet)).not.toHaveBeenCalledWith("/api/v1/risk/size");
    expect(vi.mocked(apiPost)).not.toHaveBeenCalled();
  });

  it("keeps diagnostics when the journal fails", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.includes("size-journal")) {
        return Promise.reject(new Error("down"));
      }
      return Promise.resolve(diagnostics);
    });
    renderAudit();

    expect(await screen.findByText("local")).toBeInTheDocument();
    expect(screen.getByText("paper")).toBeInTheDocument();
    expect(screen.getByText("Paper size journal is unavailable. No size was invented.")).toBeInTheDocument();
    expect(screen.queryByText("No paper sizes recorded yet.")).not.toBeInTheDocument();
    expect(screen.queryByText("Shares 4")).not.toBeInTheDocument();
    expect(vi.mocked(apiPost)).not.toHaveBeenCalled();
  });

  it("shows a size-audit row and hides one that claims an order", async () => {
    mockAudit([], [auditEntry]);
    renderAudit();

    expect(await screen.findByRole("heading", { name: "BTC-USD" })).toBeInTheDocument();
    expect(screen.getByText("Action risk.size.recorded")).toBeInTheDocument();
    expect(screen.getByText("Shares 2")).toBeInTheDocument();
    expect(screen.getByText("Order submitted false")).toBeInTheDocument();
    expect(screen.getByText("No paper sizes recorded yet.")).toBeInTheDocument();
    expect(vi.mocked(apiGet)).toHaveBeenCalledWith("/api/v1/audit/log");
    expect(vi.mocked(apiPost)).not.toHaveBeenCalled();
  });

  it("does not render an audit row that says an order was submitted", async () => {
    vi.mocked(apiGet).mockImplementation((path: string) => {
      if (path.includes("/audit/log")) {
        return Promise.resolve({
          ...emptyLog,
          events: [{ ...auditEntry, order_submitted: true }],
        });
      }
      if (path.includes("size-journal")) {
        return Promise.resolve({ entries: [] });
      }
      return Promise.resolve(diagnostics);
    });
    renderAudit();

    expect(await screen.findByText("Audit log is unavailable. No event was invented.")).toBeInTheDocument();
    expect(screen.queryByText("BTC-USD")).not.toBeInTheDocument();
    expect(screen.queryByText("Action risk.size.recorded")).not.toBeInTheDocument();
    expect(screen.getByText("local")).toBeInTheDocument();
    expect(vi.mocked(apiPost)).not.toHaveBeenCalled();
  });
});
