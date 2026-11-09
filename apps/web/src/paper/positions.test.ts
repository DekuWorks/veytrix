import { describe, expect, it } from "vitest";
import { unrealisedDifference, unrealisedPercent, unrealisedPercentLine } from "./positions";

describe("unrealised percent of entry", () => {
  it("shows a gain, a loss, and a flat print", () => {
    expect(unrealisedPercentLine("110.00", "100.00")).toBe("Unrealised percent +10.00%.");
    expect(unrealisedPercentLine("90.00", "100.00")).toBe("Unrealised percent -10.00%.");
    expect(unrealisedPercentLine("100.00", "100.00")).toBe("Unrealised percent 0.00%.");
    expect(unrealisedPercent("100.005", "100")).toBe("+0.01%");
  });

  it("does not invent a percent when the last trade or the entry is missing", () => {
    expect(unrealisedPercent("", "100.00")).toBeNull();
    expect(unrealisedPercentLine("", "100.00")).toBe("Unrealised percent is unavailable.");
    expect(unrealisedPercent("110.00", "")).toBeNull();
    expect(unrealisedPercent("110.00", "0")).toBeNull();
    expect(unrealisedPercent("110.00", "0.00")).toBeNull();
    expect(unrealisedPercent("nope", "100.00")).toBeNull();
    expect(unrealisedDifference("110.00", "100.00", 2)).toBe("20");
  });
});
