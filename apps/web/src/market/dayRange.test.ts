import { describe, expect, it } from "vitest";
import { dayRange, dayRangeLine, inProgressDayRange } from "./dayRange";

describe("in-progress day range", () => {
  it("quantizes high minus low half-up to the cent", () => {
    expect(dayRange("110.50", "100.25")).toEqual({
      state: "ready",
      high: "110.50",
      low: "100.25",
      usd: "10.25",
    });
    expect(dayRange("10.009", "10.004")).toEqual({
      state: "ready",
      high: "10.01",
      low: "10.00",
      usd: "0.01",
    });
  });

  it("treats a flat bar as zero and a missing or inverted bar as unavailable", () => {
    expect(dayRange("40.00", "40.00")).toEqual({
      state: "ready",
      high: "40.00",
      low: "40.00",
      usd: "0.00",
    });
    expect(dayRange("", "10.00")).toEqual({ state: "unavailable" });
    expect(dayRange("9.00", "10.00")).toEqual({ state: "unavailable" });
    expect(dayRangeLine({ state: "unavailable" })).toBe("Day range is unavailable.");
  });

  it("uses the latest candle and ignores an older high and low", () => {
    expect(
      inProgressDayRange([
        { bar_start: "2026-11-07T00:00:00Z", high: "1.00", low: "0.50" },
        { bar_start: "2026-11-08T00:00:00Z", high: "110.50", low: "100.25" },
      ]),
    ).toEqual({
      state: "ready",
      high: "110.50",
      low: "100.25",
      usd: "10.25",
    });
    expect(inProgressDayRange([])).toEqual({ state: "unavailable" });
  });
});