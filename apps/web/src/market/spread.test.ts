import { describe, expect, it } from "vitest";
import { quoteSpread, spreadLine } from "./spread";

describe("bid-ask spread", () => {
  it("quantizes a normal spread to cents and basis points", () => {
    expect(quoteSpread("100.00", "100.10")).toEqual({
      state: "ready",
      usd: "0.10",
      basisPoints: "10.00",
    });
    expect(quoteSpread("10.004", "10.009")).toEqual({
      state: "ready",
      usd: "0.01",
      basisPoints: "9.99",
    });
  });

  it("treats a locked book as zero and a crossed or missing ask as unavailable", () => {
    expect(quoteSpread("50.00", "50.00")).toEqual({
      state: "ready",
      usd: "0.00",
      basisPoints: "0.00",
    });
    expect(quoteSpread("10.00", "9.50")).toEqual({ state: "unavailable" });
    expect(quoteSpread("10.00", "")).toEqual({ state: "unavailable" });
    expect(quoteSpread("10.00", "nope")).toEqual({ state: "unavailable" });
    expect(spreadLine("10.00", "9.50")).toBe("Spread is unavailable.");
    expect(spreadLine("100.00", "100.10")).toBe("Spread $0.10 (10.00 bp).");
  });
});