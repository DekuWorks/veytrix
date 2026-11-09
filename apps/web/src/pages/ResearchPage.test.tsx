import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiDelete, apiGet, apiPost } from "../api/client";
import type { ResearchNoteResponse, SourceEventResponse } from "../api/types";
import { AppRoutes } from "../App";

vi.mock("../api/client", () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiDelete: vi.fn(),
}));

const saved: ResearchNoteResponse = {
  id: "note-1",
  title: "Desk check",
  body: "One line on this machine.",
  created_at: "2026-11-08T05:20:00Z",
};

const sourceEvent: SourceEventResponse = {
  id: "event-1",
  title: "Payrolls",
  source: "Bureau of Labor Statistics release",
  event_time: "2026-11-08T13:30:00Z",
  first_public_at: "2026-11-08T13:30:05Z",
  recorded_at: "2026-11-08T13:31:00Z",
  execution_permitted: false,
  order_submitted: false,
};

function renderResearch() {
  return render(
    <MemoryRouter initialEntries={["/research"]}>
      <AppRoutes />
    </MemoryRouter>,
  );
}

function mockLists(notes: ResearchNoteResponse[] = [], events: SourceEventResponse[] = []) {
  vi.mocked(apiGet).mockImplementation((path: string) => {
    if (path.includes("source-events")) {
      return Promise.resolve({ events });
    }
    return Promise.resolve({ notes });
  });
}

describe("research notes", () => {
  beforeEach(() => {
    vi.mocked(apiGet).mockReset();
    vi.mocked(apiPost).mockReset();
    vi.mocked(apiDelete).mockReset();
    mockLists();
  });

  it("shows the empty state, then a note saved through the research route", async () => {
    vi.mocked(apiPost).mockResolvedValue(saved);
    renderResearch();

    expect(await screen.findByText("No research notes recorded yet.")).toBeInTheDocument();
    expect(screen.getByText(/Not instructions to trade/)).toBeInTheDocument();
    expect(
      screen.getByText("Research notes stored on this machine. Not instructions to trade. No order is sent."),
    ).toBeInTheDocument();
    const notes = screen.getByRole("form", { name: "Research notes" });
    fireEvent.change(within(notes).getByRole("textbox", { name: "Title" }), {
      target: { value: "Desk check" },
    });
    fireEvent.change(within(notes).getByRole("textbox", { name: "Note" }), {
      target: { value: "One line on this machine." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add note" }));

    expect(await screen.findByRole("heading", { name: "Desk check" })).toBeInTheDocument();
    expect(screen.getByText("One line on this machine.")).toBeInTheDocument();
    expect(screen.queryByText("No research notes recorded yet.")).not.toBeInTheDocument();
    expect(vi.mocked(apiPost)).toHaveBeenCalledWith("/api/v1/research/notes", {
      title: "Desk check",
      body: "One line on this machine.",
    });
    expect(vi.mocked(apiGet)).toHaveBeenCalledWith("/api/v1/research/notes");
    expect(vi.mocked(apiPost)).not.toHaveBeenCalledWith("/api/v1/risk/size", expect.anything());
    expect(vi.mocked(apiPost)).not.toHaveBeenCalledWith(
      "/api/v1/portfolio/positions",
      expect.anything(),
    );
  });

  it("does not show a note when the store rejects the save", async () => {
    vi.mocked(apiPost).mockRejectedValue(new Error("down"));
    renderResearch();

    expect(await screen.findByText("No research notes recorded yet.")).toBeInTheDocument();
    const notes = screen.getByRole("form", { name: "Research notes" });
    fireEvent.change(within(notes).getByRole("textbox", { name: "Title" }), {
      target: { value: "Desk check" },
    });
    fireEvent.change(within(notes).getByRole("textbox", { name: "Note" }), {
      target: { value: "One line on this machine." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add note" }));

    expect(
      await screen.findByText("The research note store is unavailable. This note was not saved."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Desk check" })).not.toBeInTheDocument();
    expect(screen.getByText("No research notes recorded yet.")).toBeInTheDocument();
  });

  it("removes a saved note", async () => {
    mockLists([saved]);
    vi.mocked(apiDelete).mockResolvedValue(undefined);
    renderResearch();

    expect(await screen.findByRole("heading", { name: "Desk check" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Delete note" }));

    expect(await screen.findByText("No research notes recorded yet.")).toBeInTheDocument();
    expect(vi.mocked(apiDelete)).toHaveBeenCalledWith("/api/v1/research/notes/note-1");
  });
});

const NOTE_NOW = Date.parse("2026-11-08T05:00:00.000Z");

function agedNote(createdAt: string): ResearchNoteResponse {
  return {
    id: "note-age",
    title: "Desk check",
    body: "One line on this machine.",
    created_at: createdAt,
  };
}

describe("research note age", () => {
  beforeEach(() => {
    vi.useRealTimers();
    vi.mocked(apiGet).mockReset();
    vi.mocked(apiPost).mockReset();
    vi.mocked(apiDelete).mockReset();
    mockLists();
    vi.spyOn(Date, "now").mockReturnValue(NOTE_NOW);
  });

  afterEach(() => {
    vi.mocked(Date.now).mockRestore();
    vi.useRealTimers();
  });

  it("shows 2 minutes for a note 125 seconds old", async () => {
    mockLists([agedNote(new Date(NOTE_NOW - 125_000).toISOString())]);
    renderResearch();

    expect(await screen.findByRole("heading", { name: "Desk check" })).toBeInTheDocument();
    expect(screen.getByText("One line on this machine.")).toBeInTheDocument();
    expect(screen.getByText("Note age 2 minutes.")).toBeInTheDocument();
    expect(
      screen.getByText("Age of this note on this machine. Not an instruction to trade. No order is sent."),
    ).toBeInTheDocument();
    expect(screen.getByText(/Not instructions to trade/)).toBeInTheDocument();
    expect(vi.mocked(apiGet)).toHaveBeenCalledTimes(2);
    expect(vi.mocked(apiGet)).toHaveBeenCalledWith("/api/v1/research/notes");
    expect(vi.mocked(apiGet)).toHaveBeenCalledWith("/api/v1/research/source-events");
    expect(vi.mocked(apiPost)).not.toHaveBeenCalled();
  });

  it("shows 0 minutes for a note 30 seconds old", async () => {
    mockLists([agedNote(new Date(NOTE_NOW - 30_000).toISOString())]);
    renderResearch();

    expect(await screen.findByText("Note age 0 minutes.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Desk check" })).toBeInTheDocument();
    expect(vi.mocked(apiPost)).not.toHaveBeenCalled();
  });

  it("keeps a note when created_at cannot be parsed", async () => {
    mockLists([agedNote("2026-11-08Tnot-a-time")]);
    renderResearch();

    expect(await screen.findByRole("heading", { name: "Desk check" })).toBeInTheDocument();
    expect(screen.getByText("One line on this machine.")).toBeInTheDocument();
    expect(screen.getByText("Recorded at 2026-11-08Tnot-a-time.")).toBeInTheDocument();
    expect(screen.getByText("Note age is unavailable.")).toBeInTheDocument();
    expect(screen.queryByText(/Note age \d/)).not.toBeInTheDocument();
  });

  it("keeps an empty list empty", async () => {
    mockLists();
    renderResearch();

    expect(await screen.findByText("No research notes recorded yet.")).toBeInTheDocument();
    expect(screen.queryByText(/Note age/)).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Desk check" })).not.toBeInTheDocument();
    expect(vi.mocked(apiPost)).not.toHaveBeenCalled();
  });
});

describe("source events", () => {
  beforeEach(() => {
    vi.useRealTimers();
    vi.mocked(apiGet).mockReset();
    vi.mocked(apiPost).mockReset();
    vi.mocked(apiDelete).mockReset();
    mockLists();
  });

  it("shows an empty source-event list", async () => {
    renderResearch();

    expect(await screen.findByText("No source events recorded yet.")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        name: "Source events stored on this machine. Not news. Not a trading signal. No order is sent.",
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add source event" })).toBeInTheDocument();
    expect(screen.queryByText(/Record age/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Public lag/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Move age/)).not.toBeInTheDocument();
    expect(screen.getByText("No research notes recorded yet.")).toBeInTheDocument();
    expect(vi.mocked(apiPost)).not.toHaveBeenCalled();
    expect(vi.mocked(apiGet)).toHaveBeenCalledWith("/api/v1/research/source-events");
  });

  it("shows a fixture row's source, event time, and first public time", async () => {
    mockLists([], [sourceEvent]);
    renderResearch();

    expect(await screen.findByRole("heading", { name: "Payrolls" })).toBeInTheDocument();
    expect(screen.getByText("Source Bureau of Labor Statistics release")).toBeInTheDocument();
    expect(screen.getByText("Event time 2026-11-08T13:30:00Z")).toBeInTheDocument();
    expect(screen.getByText("First public time 2026-11-08T13:30:05Z")).toBeInTheDocument();
    expect(screen.getByText("Public lag 0 minutes.")).toBeInTheDocument();
    expect(
      screen.getByText(
        "First public time minus the event time. Not news. Not a trading signal. No order is sent.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText("No source events recorded yet.")).not.toBeInTheDocument();
    expect(screen.queryByText(/Move age/)).not.toBeInTheDocument();
    expect(vi.mocked(apiPost)).not.toHaveBeenCalled();
    expect(vi.mocked(apiPost)).not.toHaveBeenCalledWith("/api/v1/risk/size", expect.anything());
    expect(vi.mocked(apiPost)).not.toHaveBeenCalledWith(
      "/api/v1/portfolio/positions",
      expect.anything(),
    );
  });

  it("shows 1 minute when first public time is 90 seconds later", async () => {
    mockLists([], [
      {
        ...sourceEvent,
        event_time: "2026-11-08T13:30:00Z",
        first_public_at: "2026-11-08T13:31:30Z",
      },
    ]);
    renderResearch();

    expect(await screen.findByRole("heading", { name: "Payrolls" })).toBeInTheDocument();
    expect(screen.getByText("Public lag 1 minute.")).toBeInTheDocument();
    expect(screen.getByText("Event time 2026-11-08T13:30:00Z")).toBeInTheDocument();
    expect(screen.getByText("First public time 2026-11-08T13:31:30Z")).toBeInTheDocument();
    expect(vi.mocked(apiPost)).not.toHaveBeenCalled();
  });

  it("shows -1 minute when first public time is 90 seconds earlier", async () => {
    mockLists([], [
      {
        ...sourceEvent,
        event_time: "2026-11-08T13:30:00Z",
        first_public_at: "2026-11-08T13:28:30Z",
      },
    ]);
    renderResearch();

    expect(await screen.findByText("Public lag -1 minute.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Payrolls" })).toBeInTheDocument();
    expect(vi.mocked(apiPost)).not.toHaveBeenCalled();
  });

  it("shows 0 minutes when the timestamps are 30 seconds apart", async () => {
    mockLists([], [
      {
        ...sourceEvent,
        event_time: "2026-11-08T13:30:00Z",
        first_public_at: "2026-11-08T13:30:30Z",
      },
    ]);
    renderResearch();

    expect(await screen.findByText("Public lag 0 minutes.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Payrolls" })).toBeInTheDocument();
    expect(vi.mocked(apiPost)).not.toHaveBeenCalled();
  });

  it("keeps the row when a timestamp cannot be parsed", async () => {
    mockLists([], [
      {
        ...sourceEvent,
        event_time: "2026-11-08Tnot-a-time",
        first_public_at: "2026-11-08T13:30:05Z",
      },
    ]);
    renderResearch();

    expect(await screen.findByRole("heading", { name: "Payrolls" })).toBeInTheDocument();
    expect(screen.getByText("Source Bureau of Labor Statistics release")).toBeInTheDocument();
    expect(screen.getByText("Event time 2026-11-08Tnot-a-time")).toBeInTheDocument();
    expect(screen.getByText("Public lag is unavailable.")).toBeInTheDocument();
    expect(screen.queryByText(/Public lag -?\d/)).not.toBeInTheDocument();
    expect(vi.mocked(apiPost)).not.toHaveBeenCalled();
  });
});
