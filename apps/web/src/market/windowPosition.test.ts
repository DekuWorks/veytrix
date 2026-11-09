import { describe, expect, it } from "vitest";
import { windowPosition, windowPositionLine } from "./windowPosition";

describe("window position", () => {
  it("places the close at the low, the high, and the middle", () => {
    expect(windowPositionLine(windowPosition("50.00", "100.00", "50.00"))).toBe("Position in the window 0.00%.");
    expect(windowPositionLine(windowPosition("100.00", "100.00", "50.00"))).toBe("Position in the window 100.00%.");
    expect(windowPositionLine(windowPosition("75.00", "100.00", "50.00"))).toBe("Position in the window 50.00%.");
  });

  it("keeps a close above the high and leaves the extremes unchanged", () => {
    const high = "100.00";
    const low = "50.00";
    const position = windowPosition("150.00", high, low);

    expect(high).toBe("100.00");
    expect(low).toBe("50.00");
    expect(position).toEqual({ state: "ready", percent: "200.00", outside: true });
    expect(windowPositionLine(position)).toBe("Position in the window 200.00%. Close is outside the window.");
  });

  it("does not invent a percent for a flat window or a missing low", () => {
    expect(windowPosition("40.00", "40.00", "40.00")).toEqual({ state: "unavailable" });
    expect(windowPositionLine(windowPosition("40.00", "40.00", "40.00"))).toBe(
      "Position in the window is unavailable.",
    );
    expect(windowPosition("10.00", "12.00", "")).toEqual({ state: "unavailable" });
    expect(windowPositionLine(windowPosition("10.00", "12.00", ""))).toBe("Position in the window is unavailable.");
    expect(windowPosition("10.00", "9.00", "12.00")).toEqual({ state: "unavailable" });
  });
});
