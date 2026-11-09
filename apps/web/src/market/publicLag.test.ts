import { describe, expect, it } from "vitest";
import { publicLagLine, publicLagMinutes } from "./publicLag";

const EVENT = "2026-11-08T13:30:00Z";

describe("public lag in whole minutes", () => {
  it("truncates 90 seconds toward zero to 1 minute", () => {
    const firstPublic = "2026-11-08T13:31:30Z";
    expect(publicLagMinutes(EVENT, firstPublic)).toBe(1);
    expect(publicLagLine(EVENT, firstPublic)).toBe("Public lag 1 minute.");
  });

  it("truncates -90 seconds toward zero to -1 minute", () => {
    const firstPublic = "2026-11-08T13:28:30Z";
    expect(publicLagMinutes(EVENT, firstPublic)).toBe(-1);
    expect(publicLagLine(EVENT, firstPublic)).toBe("Public lag -1 minute.");
  });

  it("treats 30 seconds as 0 minutes", () => {
    const firstPublic = "2026-11-08T13:30:30Z";
    expect(publicLagMinutes(EVENT, firstPublic)).toBe(0);
    expect(publicLagLine(EVENT, firstPublic)).toBe("Public lag 0 minutes.");
  });

  it("does not invent a lag when a timestamp cannot be parsed", () => {
    expect(publicLagMinutes("2026-11-08Tnot-a-time", "2026-11-08T13:30:05Z")).toBeNull();
    expect(publicLagLine("2026-11-08Tnot-a-time", "2026-11-08T13:30:05Z")).toBe(
      "Public lag is unavailable.",
    );
    expect(publicLagLine(EVENT, "")).toBe("Public lag is unavailable.");
  });
});
