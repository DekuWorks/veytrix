const DECIMAL = /^-?\d+(?:\.\d+)?$/;

type Scaled = {
  negative: boolean;
  units: bigint;
  scale: number;
};

type Measured = {
  difference: bigint;
  entryUnits: bigint;
  scale: number;
};

export type StopDistance = {
  usd: string;
  percent: string;
};

export const STOP_DISTANCE_NOTE =
  "Distance from entry to stop, as a share of the entry. The dollar distance is entry minus stop. The stop is not enforced. No order is sent.";

function parseDecimal(value: string): Scaled | null {
  if (!DECIMAL.test(value)) {
    return null;
  }
  const negative = value.startsWith("-");
  const unsigned = negative ? value.slice(1) : value;
  const [whole, fraction = ""] = unsigned.split(".");
  const units = BigInt(`${whole}${fraction}`);
  if (units === 0n) {
    return { negative: false, units: 0n, scale: fraction.length };
  }
  return { negative, units, scale: fraction.length };
}

function signedUnits(value: Scaled, scale: number): bigint {
  const units = value.units * 10n ** BigInt(scale - value.scale);
  return value.negative ? -units : units;
}

function formatFixed(units: bigint, prefix: string): string {
  const digits = units.toString().padStart(3, "0");
  const whole = digits.slice(0, -2).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `${prefix}${whole}.${digits.slice(-2)}`;
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

function measure(entry: string, stop: string): Measured | null {
  const entryScaled = parseDecimal(entry);
  const stopScaled = parseDecimal(stop);
  if (entryScaled === null || stopScaled === null || entryScaled.negative || entryScaled.units === 0n) {
    return null;
  }
  const scale = Math.max(entryScaled.scale, stopScaled.scale);
  const entryUnits = signedUnits(entryScaled, scale);
  const stopUnits = signedUnits(stopScaled, scale);
  if (stopUnits >= entryUnits) {
    return null;
  }
  return { difference: entryUnits - stopUnits, entryUnits, scale };
}

export function stopDistance(entry: string, stop: string): StopDistance | null {
  const measured = measure(entry, stop);
  if (measured === null) {
    return null;
  }
  const cents = quantizeHalfUp(measured.difference, measured.scale, 2);
  const numerator = measured.difference * 10_000n;
  const quotient = numerator / measured.entryUnits;
  const remainder = numerator % measured.entryUnits;
  const percentUnits = remainder * 2n >= measured.entryUnits ? quotient + 1n : quotient;
  return {
    usd: `${formatFixed(cents, "$")}`,
    percent: `${formatFixed(percentUnits, "")}%`,
  };
}

export function stopDistancePercent(entry: string, stop: string): string | null {
  return stopDistance(entry, stop)?.percent ?? null;
}

export function stopDistanceLine(entry: string, stop: string): string {
  const distance = stopDistance(entry, stop);
  if (distance === null) {
    return "Stop distance is unavailable.";
  }
  return `Stop distance ${distance.usd} (${distance.percent}).`;
}
