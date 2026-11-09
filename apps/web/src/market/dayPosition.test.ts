import { describe, expect, it } from "vitest";
import { dayPosition, dayPositionLine } from "./dayPosition";

describe("day position", () => {
  it("quantizes the share of the range half-up to 0.01 percentage points", () => {
    expect(dayPosition("100.00", "110.00", "100.00")).toEqual({
      state: "ready",
      percent: "0.00",
      outside: false,
    });
    expect(dayPosition("110.00", "110.00", "100.00")).toEqual({
      state: "ready",
      percent: "100.00",
      outside: false,
    });
    expect(dayPosition("105.00", "110.00", "100.00")).toEqual({
      state: "ready",
      percent: "50.00",
      outside: false,
    });
    expect(dayPosition("1", "3", "0")).toEqual({ state: "ready", percent: "33.33", outside: false });
    expect(dayPosition("2", "3", "0")).toEqual({ state: "ready", percent: "66.67", outside: false });
  });

  it("keeps a print outside the candle and does not invent a percent for a flat or broken range", () => {
    const above = dayPosition("120.00", "110.00", "100.00");
    expect(above).toEqual({ state: "ready", percent: "200.00", outside: true });
    expect(dayPositionLine(above)).toBe("Position in the day 200.00%. Print is outside the daily candle.");
    const below = dayPosition("90.00", "110.00", "100.00");
    expect(below).toEqual({ state: "ready", percent: "-100.00", outside: true });
    expect(dayPosition("40.00", "40.00", "40.00")).toEqual({ state: "unavailable" });
    expect(dayPosition("10.00", "12.00", "")).toEqual({ state: "unavailable" });
    expect(dayPosition("10.00", "9.00", "10.00")).toEqual({ state: "unavailable" });
    expect(dayPositionLine({ state: "unavailable" })).toBe("Position in the day is unavailable.");
  });
});