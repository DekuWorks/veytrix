import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppRoutes } from "../App";

describe("worldview route", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: async () => ({
            features: [
              {
                id: "test-quake",
                geometry: { coordinates: [-122.4, 37.8, 8] },
                properties: { mag: 4.8, place: "near test harbour", time: 1_700_000_000_000 },
              },
            ],
          }),
        }),
      ),
    );
  });

  it("shows keyless research layers and refuses a trading control", async () => {
    render(
      <MemoryRouter initialEntries={["/worldview"]}>
        <AppRoutes />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Worldview" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Worldview" })).toHaveAttribute("href", "/worldview");
    expect(screen.getAllByText(/Data courtesy of the U.S. Geological Survey/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Not stored/)).toBeInTheDocument();
    expect(screen.getAllByText(/No order is sent/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Needs an AISStream key/)).toBeInTheDocument();
    expect(screen.getByText(/metered Google Maps key/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /order|enable|sign|withdraw|topstep/i })).not.toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /near test harbour/i })).toBeInTheDocument();

    const earthquakes = screen.getByRole("button", { name: "Earthquakes" });
    expect(earthquakes).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(earthquakes);
    expect(earthquakes).toHaveAttribute("aria-pressed", "false");
  });
});
