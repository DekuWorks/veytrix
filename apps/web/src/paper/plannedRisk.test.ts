import { describe, expect, it } from "vitest";
import { plannedRiskPercent, plannedRiskPercentLine } from "./plannedRisk";

describe("planned risk percent of equity", () => {
  it("shows a normal share and a zero planned risk", () => {
    expect(plannedRiskPercentLine("400", "100000")).toBe("Planned risk percent 0.40%.");
    expect(plannedRiskPercent("400.00", "100000.00")).toBe("0.40%");
    expect(plannedRiskPercentLine("0", "100000")).toBe("Planned risk percent 0.00%.");
    expect(plannedRiskPercentLine("0.00", "100000.00")).toBe("Planned risk percent 0.00%.");
  });

  it("does not invent a percent when equity is missing or zero", () => {
    expect(plannedRiskPercent("400", "0")).toBeNull();
    expect(plannedRiskPercent("400", "0.00")).toBeNull();
    expect(plannedRiskPercentLine("400", "0")).toBe("Planned risk percent is unavailable.");
    expect(plannedRiskPercent("400", "")).toBeNull();
    expect(plannedRiskPercent("400", "nope")).toBeNull();
    expect(plannedRiskPercent("", "100000")).toBeNull();
  });
});
