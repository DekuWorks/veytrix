import { describe, expect, it } from "vitest";
import { printGapLine, printMinusClose } from "./printGap";

describe("print minus candle", () => {
  it("quantizes a positive, flat, and negative gap", () => {
    expect(printMinusClose("110.00", "100.00")).toEqual({
      state: "ready",
      usd: "+$10.00",
      percent: "+10.00%",
    });
    expect(printGapLine(printMinusClose("100.00", "100.00"))).toBe("Print minus candle $0.00 (0.00%).");
    expect(printMinusClose("90.00", "100.00")).toEqual({
      state: "ready",
      usd: "-$10.00",
      percent: "-10.00%",
    });
    expect(printMinusClose("100.005", "100")).toEqual({
      state: "ready",
      usd: "+$0.01",
      percent: "+0.01%",
    });
  });

  it("does not invent a gap when the close is missing or zero", () => {
    expect(printGapLine(printMinusClose("110.00", ""))).toBe("Print minus candle is unavailable.");
    expect(printGapLine(printMinusClose("110.00", "0.00"))).toBe("Print minus candle is unavailable.");
    expect(printGapLine(printMinusClose("", "100.00"))).toBe("Print minus candle is unavailable.");
  });
});