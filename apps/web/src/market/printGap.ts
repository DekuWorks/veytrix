const DECIMAL = /^\d+(?:\.\d+)?$/;

type Scaled = {
  units: bigint;
  scale: number;
};

export const PRINT_GAP_NOTE =
  "Last trade minus the latest 1-minute close. The close is not the live print. Not a trading signal. No order is sent.";

export type PrintGap =
  | { state: "ready"; usd: string; percent: string }
  | { state: "unavailable" };

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

function signedUsd(units: bigint): string {
  if (units === 0n) {
    return "$0.00";
  }
  const negative = units < 0n;
  const body = formatFixed(negative ? -units : units, 2);
  return negative ? `-$${body}` : `+$${body}`;
}

function signedPercent(units: bigint): string {
  if (units === 0n) {
    return "0.00%";
  }
  const negative = units < 0n;
  const body = formatFixed(negative ? -units : units, 2);
  return negative ? `-${body}%` : `+${body}%`;
}

export function printMinusClose(last: string, close: string): PrintGap {
  const lastScaled = parseDecimal(last);
  const closeScaled = parseDecimal(close);
  if (lastScaled === null || closeScaled === null) {
    return { state: "unavailable" };
  }
  const scale = Math.max(lastScaled.scale, closeScaled.scale);
  const lastUnits = lastScaled.units * 10n ** BigInt(scale - lastScaled.scale);
  const closeUnits = closeScaled.units * 10n ** BigInt(scale - closeScaled.scale);
  if (closeUnits === 0n) {
    return { state: "unavailable" };
  }
  const offset = lastUnits - closeUnits;
  const negative = offset < 0n;
  const magnitude = negative ? -offset : offset;
  const usdUnits = quantizeHalfUp(magnitude, scale, 2);
  const quotient = (magnitude * 10_000n) / closeUnits;
  const remainder = (magnitude * 10_000n) % closeUnits;
  const percentUnits = remainder * 2n >= closeUnits ? quotient + 1n : quotient;
  return {
    state: "ready",
    usd: signedUsd(negative ? -usdUnits : usdUnits),
    percent: signedPercent(negative ? -percentUnits : percentUnits),
  };
}

export function printGapLine(gap: PrintGap): string {
  if (gap.state === "unavailable") {
    return "Print minus candle is unavailable.";
  }
  return `Print minus candle ${gap.usd} (${gap.percent}).`;
}
