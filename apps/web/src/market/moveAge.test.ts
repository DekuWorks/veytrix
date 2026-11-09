import { describe, expect, it } from "vitest";
import { moveAgeLine, moveAgeMinutes } from "./moveAge";

const NOW = Date.parse("2026-11-08T05:00:00.000Z");

describe("move age in whole minutes", () => {
  it("rounds 125 seconds down to 2 minutes", () => {
    const start = new Date(NOW - 125_000).toISOString();
    expect(moveAgeMinutes(start, NOW)).toBe(2);
    expect(moveAgeLine(start, NOW)).toBe("Move age 2 minutes.");
  });

  it("rounds 30 seconds down to 0 minutes", () => {
    const start = new Date(NOW - 30_000).toISOString();
    expect(moveAgeMinutes(start, NOW)).toBe(0);
    expect(moveAgeLine(start, NOW)).toBe("Move age 0 minutes.");
  });

  it("does not invent an age when the candle time cannot be parsed", () => {
    expect(moveAgeMinutes("not-a-time", NOW)).toBeNull();
    expect(moveAgeLine("not-a-time", NOW)).toBe("Move age is unavailable.");
    expect(moveAgeLine("", NOW)).toBe("Move age is unavailable.");
  });
});
