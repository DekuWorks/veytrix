import { describe, expect, it } from "vitest";
import { parseExchangeTime, printStatus } from "./freshness";

const NOW = Date.parse("2026-11-08T05:40:00.000Z");

describe("exchange time freshness", () => {
  it("truncates a Coinbase fraction longer than milliseconds before parsing", () => {
    const raw = "2026-11-08T05:39:39.123456789Z";
    expect(parseExchangeTime(raw)).toBe(Date.parse("2026-11-08T05:39:39.123Z"));
    expect(printStatus(raw, Date.parse("2026-11-08T05:40:00.123Z"))).toEqual({
      state: "stale",
      ageSeconds: 21,
      line: "Print is stale. Age 21 seconds.",
    });
  });

  it("marks a print more than 20 seconds old and leaves a younger one current", () => {
    expect(printStatus("2026-11-08T05:39:39.000Z", NOW)).toMatchObject({
      state: "stale",
      ageSeconds: 21,
    });
    expect(printStatus("2026-11-08T05:39:55.000Z", NOW)).toEqual({ state: "current" });
    expect(printStatus("2026-11-08T05:39:40.000Z", NOW)).toEqual({ state: "current" });
  });

  it("does not treat an unreadable exchange time as current", () => {
    expect(printStatus("2026-11-08Tnot-readableZ", NOW)).toEqual({
      state: "unreadable",
      line: "Exchange time is unreadable.",
    });
  });
});
