const DECIMAL = /^\d+(?:\.\d+)?$/;

type Scaled = {
  units: bigint;
  scale: number;
};

export const DAY_RANGE_NOTE =
  "In-progress UTC day from the Coinbase daily candle. Not a settlement. No order is sent.";

export type DayRange =
  | { state: "ready"; high: string; low: string; usd: string }
  | { state: "unavailable" };

type DayBar = {
  bar_start: string;
  high: string;
  low: string;
};

function parseDecimal(value: string): Scaled | null {
  if (!DECIMAL.test(value)) {
    return null;
  }
  const [whole, fraction = ""] = value.split(".");
  return { units: BigInt(`${whole}${fraction}`), scale: fraction.length };
}

function quantizeHalfUp(units: bigint, scale: number, places: number): bigint {
  if (scale <= places) {
    return units * 10n ** BigInt(places - scale);
  }
  const divisor = 10n ** BigInt(scale - places);
  const quotient = units / divisor;
  const remainder = units % divisor;
  return remainder * 2n >= divisor ? quotient + 1n : quotient;
}

function formatFixed(units: bigint, places: number): string {
  const digits = units.toString().padStart(places + 1, "0");
  const whole = digits.slice(0, -places);
  const fraction = digits.slice(-places);
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `${grouped}.${fraction}`;
}

export function dayRange(high: string, low: string): DayRange {
  const highScaled = parseDecimal(high);
  const lowScaled = parseDecimal(low);
  if (highScaled === null || lowScaled === null) {
    return { state: "unavailable" };
  }
  const scale = Math.max(highScaled.scale, lowScaled.scale);
  const highUnits = highScaled.units * 10n ** BigInt(scale - highScaled.scale);
  const lowUnits = lowScaled.units * 10n ** BigInt(scale - lowScaled.scale);
  if (highUnits < lowUnits) {
    return { state: "unavailable" };
  }
  return {
    state: "ready",
    high: formatFixed(quantizeHalfUp(highUnits, scale, 2), 2),
    low: formatFixed(quantizeHalfUp(lowUnits, scale, 2), 2),
    usd: formatFixed(quantizeHalfUp(highUnits - lowUnits, scale, 2), 2),
  };
}

export function inProgressDayRange(bars: readonly DayBar[]): DayRange {
  let bestTime = Number.NEGATIVE_INFINITY;
  let best: DayBar | null = null;
  for (const bar of bars) {
    const time = Date.parse(bar.bar_start);
    if (Number.isNaN(time) || time < bestTime) {
      continue;
    }
    bestTime = time;
    best = bar;
  }
  if (best === null) {
    return { state: "unavailable" };
  }
  return dayRange(best.high, best.low);
}

export function dayRangeLine(range: DayRange): string {
  if (range.state === "unavailable") {
    return "Day range is unavailable.";
  }
  return `Day high $${range.high}. Day low $${range.low}. Day range $${range.usd}.`;
}
