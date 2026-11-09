import { describe, expect, it } from "vitest";
import { printAverageGapLine, printMinusAverage } from "./averageGap";

describe("print minus average", () => {
  it("shows the print above, on, and below the average", () => {
    expect(printAverageGapLine(printMinusAverage("110.00", "100.00"))).toBe(
      "Print minus average +$10.00 (+10.00%).",
    );
    expect(printAverageGapLine(printMinusAverage("100.00", "100.00"))).toBe("Print minus average $0.00 (0.00%).");
    expect(printAverageGapLine(printMinusAverage("90.00", "100.00"))).toBe(
      "Print minus average -$10.00 (-10.00%).",
    );
  });

  it("does not invent a gap when the average is missing or zero", () => {
    expect(printMinusAverage("110.00", "")).toEqual({ state: "unavailable" });
    expect(printAverageGapLine(printMinusAverage("110.00", ""))).toBe("Print minus average is unavailable.");
    expect(printMinusAverage("110.00", "0")).toEqual({ state: "unavailable" });
    expect(printMinusAverage("110.00", "0.00")).toEqual({ state: "unavailable" });
    expect(printMinusAverage("", "100.00")).toEqual({ state: "unavailable" });
  });
});
