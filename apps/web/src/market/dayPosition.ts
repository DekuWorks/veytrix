const DECIMAL = /^\d+(?:\.\d+)?$/;

type Scaled = {
  units: bigint;
  scale: number;
};

type DayBar = {
  bar_start: string;
  high: string;
  low: string;
};

export const DAY_POSITION_NOTE =
  "Share of the in-progress UTC day range, from the low. Not a trading signal. Not a settlement. No order is sent.";

export type DayPosition =
  | { state: "ready"; percent: string; outside: boolean }
  | { state: "unavailable" };

function parseDecimal(value: string): Scaled | null {
  if (!DECIMAL.test(value)) {
    return null;
  }
  const [whole, fraction = ""] = value.split(".");
  return { units: BigInt(`${whole}${fraction}`), scale: fraction.length };
}

function formatFixed(units: bigint, places: number): string {
  const digits = units.toString().padStart(places + 1, "0");
  const whole = digits.slice(0, -places);
  const fraction = digits.slice(-places);
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `${grouped}.${fraction}`;
}

export function currentDayBounds(bars: readonly DayBar[]): { high: string; low: string } | null {
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
    return null;
  }
  return { high: best.high, low: best.low };
}

export function dayPosition(last: string, high: string, low: string): DayPosition {
  const lastScaled = parseDecimal(last);
  const highScaled = parseDecimal(high);
  const lowScaled = parseDecimal(low);
  if (lastScaled === null || highScaled === null || lowScaled === null) {
    return { state: "unavailable" };
  }
  const scale = Math.max(lastScaled.scale, highScaled.scale, lowScaled.scale);
  const lastUnits = lastScaled.units * 10n ** BigInt(scale - lastScaled.scale);
  const highUnits = highScaled.units * 10n ** BigInt(scale - highScaled.scale);
  const lowUnits = lowScaled.units * 10n ** BigInt(scale - lowScaled.scale);
  if (highUnits <= lowUnits) {
    return { state: "unavailable" };
  }
  const span = highUnits - lowUnits;
  const offset = lastUnits - lowUnits;
  const negative = offset < 0n;
  const magnitude = negative ? -offset : offset;
  const numerator = magnitude * 10_000n;
  const quotient = numerator / span;
  const remainder = numerator % span;
  const rounded = remainder * 2n >= span ? quotient + 1n : quotient;
  return {
    state: "ready",
    percent: negative ? `-${formatFixed(rounded, 2)}` : formatFixed(rounded, 2),
    outside: lastUnits < lowUnits || lastUnits > highUnits,
  };
}

export function dayPositionLine(position: DayPosition): string {
  if (position.state === "unavailable") {
    return "Position in the day is unavailable.";
  }
  const line = `Position in the day ${position.percent}%.`;
  return position.outside ? `${line} Print is outside the daily candle.` : line;
}
