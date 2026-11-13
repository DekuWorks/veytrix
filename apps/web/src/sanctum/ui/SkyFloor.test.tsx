import { act, fireEvent, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Speech } from "../../comms/types";
import { SkyFloor } from "./SkyFloor";

const shot = { scale: 1, x: 0, y: 0 };

function bot(container: HTMLElement, name: string): HTMLElement {
  const found = [...container.querySelectorAll<HTMLElement>(".bot")].find((el) =>
    el.textContent?.includes(name),
  );
  if (!found) {
    throw new Error(`no avatar named ${name}`);
  }
  return found;
}

function position(el: HTMLElement): { x: number; y: number } {
  return { x: parseFloat(el.style.left), y: parseFloat(el.style.top) };
}

function floor(props: Partial<React.ComponentProps<typeof SkyFloor>> = {}) {
  return (
    <SkyFloor
      shot={shot}
      persona={() => "Desk"}
      selected={null}
      onDesk={() => undefined}
      onBoardroom={() => undefined}
      speech={{}}
      gather={[]}
      follow={null}
      onAvatar={() => undefined}
      {...props}
    />
  );
}

const speech: Speech = {
  id: "m-9",
  code: "RISK-01",
  text: "Aegis, Risk desk. Nothing is running on this desk.",
  origin: "tool_verified",
  label: "verified",
  conversationId: "c",
  conversationKind: "direct",
  participants: ["RISK-01"],
  replay: false,
  peerReply: false,
};

describe("sky floor speech and movement", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("shows no speech unless a stored message is passed in", () => {
    const { container } = render(floor());
    expect(container.querySelector(".thought")).toBeNull();
    act(() => {
      vi.advanceTimersByTime(30_000);
    });
    expect(container.querySelector(".thought")).toBeNull();
  });

  it("shows the stored message and its origin tag above the speaking desk only", () => {
    const { container } = render(floor({ speech: { "RISK-01": speech } }));
    const bubbles = container.querySelectorAll(".thought");
    expect(bubbles).toHaveLength(1);
    expect(bubbles[0].getAttribute("data-agent")).toBe("RISK-01");
    expect(bubbles[0].textContent).toContain("Aegis, Risk desk. Nothing is running on this desk.");
    expect(bubbles[0].querySelector(".cx-bubble-tag")?.textContent).toBe("verified");
    expect(bubbles[0].getAttribute("data-origin")).toBe("tool_verified");
  });

  it("marks a replayed message as a replay", () => {
    const { container } = render(floor({ speech: { "RISK-01": { ...speech, replay: true } } }));
    expect(container.querySelector(".thought.replay")).not.toBeNull();
  });

  it("walks gathered desks to the boardroom", () => {
    const { container, rerender } = render(floor());
    const home = position(bot(container, "Aegis"));
    rerender(floor({ gather: ["RISK-01", "STOCK-01", "SUPERVISOR-01"] }));
    act(() => {
      vi.advanceTimersByTime(220 * 80);
    });
    const seated = position(bot(container, "Aegis"));
    expect(seated.y).toBeGreaterThan(home.y + 5);
    expect(seated.y).toBeGreaterThan(64);
    expect(Math.abs(seated.x - 50)).toBeLessThan(20);
  });

  it("with reduced motion, jumps to the seat and back home without animation", () => {
    const original = window.matchMedia;
    window.matchMedia = ((query: string) => ({
      matches: query.includes("reduce"),
      media: query,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
    })) as unknown as typeof window.matchMedia;
    try {
      const { container, rerender } = render(floor());
      const home = position(bot(container, "Aegis"));
      rerender(floor({ gather: ["RISK-01", "STOCK-01"] }));
      const seated = position(bot(container, "Aegis"));
      expect(seated).not.toEqual(home);
      expect(seated.y).toBeGreaterThan(64);
      rerender(floor({ gather: [] }));
      expect(position(bot(container, "Aegis"))).toEqual(home);
    } finally {
      window.matchMedia = original;
    }
  });

  it("keeps the avatar clickable and reports the click", () => {
    const onDesk = vi.fn();
    const onAvatar = vi.fn();
    const { container } = render(floor({ onDesk, onAvatar }));
    fireEvent.click(bot(container, "Astra").querySelector("button")!);
    expect(onDesk).toHaveBeenCalledWith("RESEARCH-01");
    expect(onAvatar).toHaveBeenCalledWith("RESEARCH-01");
  });

  it("walks Roads off the table and Dayvid off his desk toward other people", () => {
    const { container, rerender } = render(floor());
    const table = (spot: { x: number; y: number }) => spot.x > 30 && spot.x < 70 && spot.y > 63;
    expect(table(position(bot(container, "Roads")))).toBe(false);
    expect(position(bot(container, "Dayvid"))).not.toEqual({ x: 36, y: 64 });
    act(() => {
      vi.advanceTimersByTime(220 * 30);
    });
    expect(table(position(bot(container, "Roads")))).toBe(false);
    expect(position(bot(container, "Roads")).y).toBeLessThan(63);
    rerender(floor({ gather: ["SUPERVISOR-01", "DAY-01", "RISK-01"] }));
    act(() => {
      vi.advanceTimersByTime(220 * 80);
    });
    expect(table(position(bot(container, "Roads")))).toBe(false);
    expect(table(position(bot(container, "Dayvid")))).toBe(false);
    expect(position(bot(container, "Dayvid")).y).toBeLessThan(63);
  });

  it("centres the camera on a followed desk without changing the floor", () => {
    const { container } = render(floor({ follow: "RISK-01" }));
    const camera = container.querySelector<HTMLElement>(".sky-cam")!;
    expect(camera.style.transform).toMatch(/scale\(1\.7\) translate\(-?[\d.]+%, -?[\d.]+%\)/);
    expect(container.querySelectorAll(".sky-desk")).toHaveLength(9);
    expect(container.querySelectorAll(".bot")).toHaveLength(10);
  });
});
