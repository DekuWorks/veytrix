import { describe, expect, it } from "vitest";
import { formatBaseQuantity, lastSizeLine, volumeLine } from "./baseQuantity";

describe("base quantity", () => {
  it("groups a base amount and strips trailing zeros without using a float", () => {
    expect(formatBaseQuantity("1959.85")).toBe("1,959.85");
    expect(formatBaseQuantity("2022.50285353")).toBe("2,022.50285353");
    expect(formatBaseQuantity("0.00000011")).toBe("0.00000011");
    expect(formatBaseQuantity("0.0100")).toBe("0.01");
    expect(formatBaseQuantity("0")).toBe("0");
    expect(formatBaseQuantity("0.00")).toBe("0");
  });

  it("rejects a missing or non-decimal amount", () => {
    expect(formatBaseQuantity("")).toBeNull();
    expect(formatBaseQuantity("nope")).toBeNull();
    expect(formatBaseQuantity("1e2")).toBeNull();
    expect(formatBaseQuantity("-1")).toBeNull();
    expect(volumeLine("", "BTC")).toBe("Volume is unavailable.");
    expect(lastSizeLine("nope", "ETH")).toBe("Last size is unavailable.");
  });
});
