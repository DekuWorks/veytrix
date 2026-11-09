const DECIMAL = /^\d+(?:\.\d+)?$/;

type Scaled = {
  units: bigint;
  scale: number;
};

export const WINDOW_POSITION_NOTE =
  "Share of the 1-minute window, from the low. Not a trading signal. The close is not the live print. No order is sent.";

export type WindowPosition =
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

export function windowPosition(close: string, high: string, low: string): WindowPosition {
  const closeScaled = parseDecimal(close);
  const highScaled = parseDecimal(high);
  const lowScaled = parseDecimal(low);
  if (closeScaled === null || highScaled === null || lowScaled === null) {
    return { state: "unavailable" };
  }
  const scale = Math.max(closeScaled.scale, highScaled.scale, lowScaled.scale);
  const closeUnits = closeScaled.units * 10n ** BigInt(scale - closeScaled.scale);
  const highUnits = highScaled.units * 10n ** BigInt(scale - highScaled.scale);
  const lowUnits = lowScaled.units * 10n ** BigInt(scale - lowScaled.scale);
  if (highUnits <= lowUnits) {
    return { state: "unavailable" };
  }
  const span = highUnits - lowUnits;
  const offset = closeUnits - lowUnits;
  const negative = offset < 0n;
  const magnitude = negative ? -offset : offset;
  const numerator = magnitude * 10_000n;
  const quotient = numerator / span;
  const remainder = numerator % span;
  const rounded = remainder * 2n >= span ? quotient + 1n : quotient;
  return {
    state: "ready",
    percent: negative ? `-${formatFixed(rounded, 2)}` : formatFixed(rounded, 2),
    outside: closeUnits < lowUnits || closeUnits > highUnits,
  };
}

export function windowPositionLine(position: WindowPosition): string {
  if (position.state === "unavailable") {
    return "Position in the window is unavailable.";
  }
  const line = `Position in the window ${position.percent}%.`;
  return position.outside ? `${line} Close is outside the window.` : line;
}
