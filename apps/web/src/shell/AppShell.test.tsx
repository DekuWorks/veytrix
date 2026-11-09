import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { AppRoutes } from "../App";

vi.mock("../api/client", () => ({
  apiGet: vi.fn(() => new Promise(() => undefined)),
}));

describe("dashboard shell", () => {
  it("exposes the skip link, current page, and unfinished sections", () => {
    render(
      <MemoryRouter initialEntries={["/market"]}>
        <AppRoutes />
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "Skip to content" })).toHaveAttribute("href", "#main");
    expect(screen.getByRole("link", { name: "Market" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Quant" })).toHaveAttribute("href", "/quant");
    expect(screen.getByRole("link", { name: "Events" })).toHaveAttribute("href", "/events");
    expect(screen.getByRole("link", { name: "Overview" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Risk" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Portfolio" })).toHaveAttribute("href", "/portfolio");
    expect(screen.getByRole("link", { name: "Research" })).toHaveAttribute("href", "/research");
    expect(screen.getByRole("link", { name: "Audit" })).toHaveAttribute("href", "/audit");
    expect(screen.getByRole("link", { name: "Treasury" })).toHaveAttribute("href", "/treasury");
    expect(screen.getByRole("link", { name: "System" })).toHaveAttribute("href", "/system");
    expect(screen.getByRole("link", { name: "Settings" })).toHaveAttribute("href", "/settings");
    expect(screen.queryByRole("button", { name: /not built/i })).not.toBeInTheDocument();
  });

  it("closes the navigation drawer when Escape is pressed", () => {
    render(
      <MemoryRouter initialEntries={["/risk"]}>
        <AppRoutes />
      </MemoryRouter>,
    );

    const menu = screen.getByRole("button", { name: "Open navigation" });
    fireEvent.click(menu);
    expect(menu).toHaveAttribute("aria-expanded", "true");
    fireEvent.keyDown(window, { key: "Escape" });
    expect(menu).toHaveAttribute("aria-expanded", "false");
  });
});
