import { describe, expect, it } from "vitest";
import { stopDistance, stopDistanceLine, stopDistancePercent } from "./stopDistance";

describe("stop distance from entry to stop", () => {
  it("shows $2.00 and 4.00 percent from entry 50 to stop 48", () => {
    expect(stopDistance("50", "48")).toEqual({ usd: "$2.00", percent: "4.00%" });
    expect(stopDistancePercent("50", "48")).toBe("4.00%");
    expect(stopDistanceLine("50", "48")).toBe("Stop distance $2.00 (4.00%).");
    expect(stopDistanceLine("50.00", "48.00")).toBe("Stop distance $2.00 (4.00%).");
  });

  it("keeps one unavailable line when the stop is equal, above, or missing", () => {
    expect(stopDistance("50", "50")).toBeNull();
    expect(stopDistanceLine("50", "50")).toBe("Stop distance is unavailable.");
    expect(stopDistanceLine("50", "51")).toBe("Stop distance is unavailable.");
    expect(stopDistanceLine("50", "")).toBe("Stop distance is unavailable.");
    expect(stopDistanceLine("", "48")).toBe("Stop distance is unavailable.");
    expect(stopDistanceLine("0", "0")).toBe("Stop distance is unavailable.");
    expect(stopDistancePercent("50", "51")).toBeNull();
  });
});
