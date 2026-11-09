const DECIMAL = /^-?\d+(\.\d+)?$/;

type Scaled = {
  negative: boolean;
  units: bigint;
  scale: number;
};

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

function formatScaled(signed: bigint, scale: number): string {
  const negative = signed < 0n;
  const digits = (negative ? -signed : signed).toString().padStart(scale + 1, "0");
  if (scale === 0) {
    return negative ? `-${digits}` : digits;
  }
  const whole = digits.slice(0, -scale);
  const fraction = digits.slice(-scale).replace(/0+$/, "");
  const body = fraction.length === 0 ? whole : `${whole}.${fraction}`;
  return negative ? `-${body}` : body;
}

export function unrealisedDifference(last: string, entry: string, shares: number): string | null {
  if (!Number.isSafeInteger(shares) || shares < 0) {
    return null;
  }
  const lastScaled = parseDecimal(last);
  const entryScaled = parseDecimal(entry);
  if (lastScaled === null || entryScaled === null) {
    return null;
  }
  const scale = Math.max(lastScaled.scale, entryScaled.scale);
  const lastUnits = lastScaled.units * 10n ** BigInt(scale - lastScaled.scale);
  const entryUnits = entryScaled.units * 10n ** BigInt(scale - entryScaled.scale);
  const signedLast = lastScaled.negative ? -lastUnits : lastUnits;
  const signedEntry = entryScaled.negative ? -entryUnits : entryUnits;
  return formatScaled((signedLast - signedEntry) * BigInt(shares), scale);
}

export function sumSignedDecimals(values: readonly string[]): string | null {
  if (values.length === 0) {
    return null;
  }
  const parsed: Scaled[] = [];
  let scale = 0;
  for (const value of values) {
    const item = parseDecimal(value);
    if (item === null) {
      return null;
    }
    parsed.push(item);
    scale = Math.max(scale, item.scale);
  }
  let total = 0n;
  for (const item of parsed) {
    total += signedUnits(item, scale);
  }
  return formatScaled(total, scale);
}

export function formatUsd(value: string): string | null {
  if (!DECIMAL.test(value)) {
    return null;
  }
  const negative = value.startsWith("-");
  const unsigned = negative ? value.slice(1) : value;
  const [whole, fraction] = unsigned.split(".");
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const body = fraction === undefined || fraction.length === 0 ? grouped : `${grouped}.${fraction}`;
  return negative ? `-$${body}` : `$${body}`;
}

export function formatDifferenceUsd(value: string): string | null {
  const formatted = formatUsd(value);
  if (formatted === null) {
    return null;
  }
  if (value.startsWith("-") || value === "0" || /^0\.0+$/.test(value)) {
    return formatted;
  }
  return `+${formatted}`;
}

function percentPoints(units: bigint): string {
  if (units === 0n) {
    return "0.00%";
  }
  const negative = units < 0n;
  const digits = (negative ? -units : units).toString().padStart(3, "0");
  const whole = digits.slice(0, -2).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const body = `${whole}.${digits.slice(-2)}%`;
  return negative ? `-${body}` : `+${body}`;
}

export function unrealisedPercent(last: string, entry: string): string | null {
  const lastScaled = parseDecimal(last);
  const entryScaled = parseDecimal(entry);
  if (lastScaled === null || entryScaled === null || entryScaled.units === 0n) {
    return null;
  }
  const scale = Math.max(lastScaled.scale, entryScaled.scale);
  const lastUnits = signedUnits(lastScaled, scale);
  const entryUnits = signedUnits(entryScaled, scale);
  const entryAbs = entryUnits < 0n ? -entryUnits : entryUnits;
  const numerator = (lastUnits - entryUnits) * 10_000n;
  if (numerator === 0n) {
    return percentPoints(0n);
  }
  const negative = numerator < 0n !== entryUnits < 0n;
  const absolute = numerator < 0n ? -numerator : numerator;
  const quotient = absolute / entryAbs;
  const remainder = absolute % entryAbs;
  const rounded = remainder * 2n >= entryAbs ? quotient + 1n : quotient;
  return percentPoints(negative ? -rounded : rounded);
}

export function unrealisedPercentLine(last: string, entry: string): string {
  const percent = unrealisedPercent(last, entry);
  if (percent === null) {
    return "Unrealised percent is unavailable.";
  }
  return `Unrealised percent ${percent}.`;
}

function signedUnits(value: Scaled, scale: number): bigint {
  const units = value.units * 10n ** BigInt(scale - value.scale);
  return value.negative ? -units : units;
}

function formatSignedPercent(value: string): string | null {
  if (!DECIMAL.test(value)) {
    return null;
  }
  if (value.startsWith("-") || value === "0" || /^0\.0+$/.test(value)) {
    return `${value}%`;
  }
  return `+${value}%`;
}

export function distanceToStop(
  last: string,
  stop: string,
): { usd: string; percent: string } | null {
  const lastScaled = parseDecimal(last);
  const stopScaled = parseDecimal(stop);
  if (
    lastScaled === null ||
    stopScaled === null ||
    stopScaled.negative ||
    stopScaled.units === 0n
  ) {
    return null;
  }
  const scale = Math.max(lastScaled.scale, stopScaled.scale);
  const lastUnits = signedUnits(lastScaled, scale);
  const stopUnits = signedUnits(stopScaled, scale);
  const usd = formatDifferenceUsd(formatScaled(lastUnits - stopUnits, scale));
  const scaled = (lastUnits - stopUnits) * 10_000n;
  const negative = scaled < 0n;
  const absolute = negative ? -scaled : scaled;
  const quotient = absolute / stopUnits;
  const remainder = absolute % stopUnits;
  const rounded = remainder * 2n >= stopUnits ? quotient + 1n : quotient;
  const percent = formatSignedPercent(formatScaled(negative ? -rounded : rounded, 2));
  if (usd === null || percent === null) {
    return null;
  }
  return { usd, percent };
}
