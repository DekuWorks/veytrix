import { describe, expect, it } from "vitest";
import { noteAgeLine } from "./noteAge";
import { moveAgeMinutes } from "./moveAge";

const NOW = Date.parse("2026-11-08T05:00:00.000Z");

describe("note age in whole minutes", () => {
  it("rounds 125 seconds down to 2 minutes", () => {
    const createdAt = new Date(NOW - 125_000).toISOString();
    expect(moveAgeMinutes(createdAt, NOW)).toBe(2);
    expect(noteAgeLine(createdAt, NOW)).toBe("Note age 2 minutes.");
  });

  it("rounds 30 seconds down to 0 minutes", () => {
    const createdAt = new Date(NOW - 30_000).toISOString();
    expect(noteAgeLine(createdAt, NOW)).toBe("Note age 0 minutes.");
  });

  it("does not invent an age when created_at cannot be parsed", () => {
    expect(noteAgeLine("2026-11-08Tnot-a-time", NOW)).toBe("Note age is unavailable.");
    expect(noteAgeLine("", NOW)).toBe("Note age is unavailable.");
  });
});
