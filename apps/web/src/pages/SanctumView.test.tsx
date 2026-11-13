import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiGet } from "../api/client";
import { SanctumPage } from "./SanctumPage";
import { SHOTS, VIEW_STORAGE_KEY, loadView } from "../sanctum/viewPreference";

vi.mock("../api/client", () => ({
  apiGet: vi.fn(() => Promise.reject(new Error("offline"))),
  apiPost: vi.fn(() => Promise.reject(new Error("offline"))),
  apiPatch: vi.fn(() => Promise.reject(new Error("offline"))),
}));

describe("sanctum sky view memory", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.mocked(apiGet).mockClear();
  });

  it("restores the boardroom and returns to the sky view", () => {
    window.localStorage.setItem(
      VIEW_STORAGE_KEY,
      JSON.stringify({ rail: "boardroom", camera: "meeting", shot: SHOTS.meeting }),
    );

    render(
      <MemoryRouter>
        <SanctumPage />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Wednesday boardroom" })).toBeInTheDocument();
    expect(screen.getByText(/No calendar event is created/)).toBeInTheDocument();
    expect(screen.getByText("Claude: disconnected")).toBeInTheDocument();
    expect(screen.getByText("Model speech: simulated")).toBeInTheDocument();
    expect(screen.getByText("Alpaca paper: disconnected")).toBeInTheDocument();
    expect(screen.queryByText("Claude: connected")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Return to Sky View" }));

    expect(screen.queryByRole("heading", { name: "Wednesday boardroom" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Return to Sky View" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(loadView(window.localStorage)).toEqual({
      rail: "sky",
      camera: "sky",
      shot: { scale: 1, x: 0, y: 0 },
    });
  });

  it("remembers a camera preset after it is chosen", () => {
    render(
      <MemoryRouter>
        <SanctumPage />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Meeting" }));

    expect(loadView(window.localStorage).rail).toBe("boardroom");
    expect(loadView(window.localStorage).camera).toBe("meeting");
    expect(screen.getByRole("heading", { name: "Wednesday boardroom" })).toBeInTheDocument();
  });
});
