const DECIMAL = /^\d+(?:\.\d+)?$/;

type Scaled = {
  units: bigint;
  scale: number;
};

export const SPREAD_NOTE =
  "Bid-ask spread from the Coinbase print. Not a consolidated quote. No order is sent.";

export type QuoteSpread =
  | { state: "ready"; usd: string; basisPoints: string }
  | { state: "unavailable" };

function parseDecimal(value: string): Scaled | null {
  if (!DECIMAL.test(value)) {
    return null;
  }
  const [whole, fraction = ""] = value.split(".");
  return { units: BigInt(`${whole}${fraction}`), scale: fraction.length };
}

function align(left: Scaled, right: Scaled): { bid: bigint; ask: bigint; scale: number } {
  const scale = Math.max(left.scale, right.scale);
  return {
    bid: left.units * 10n ** BigInt(scale - left.scale),
    ask: right.units * 10n ** BigInt(scale - right.scale),
    scale,
  };
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

function basisPoints(cents: bigint, sum: bigint, scale: number): string {
  if (cents === 0n || sum === 0n) {
    return "0.00";
  }
  const numerator = cents * 20_000n * 10n ** BigInt(scale);
  const quotient = numerator / sum;
  const remainder = numerator % sum;
  const rounded = remainder * 2n >= sum ? quotient + 1n : quotient;
  return formatFixed(rounded, 2);
}

export function quoteSpread(bid: string, ask: string): QuoteSpread {
  const bidScaled = parseDecimal(bid);
  const askScaled = parseDecimal(ask);
  if (bidScaled === null || askScaled === null) {
    return { state: "unavailable" };
  }
  const aligned = align(bidScaled, askScaled);
  if (aligned.ask < aligned.bid) {
    return { state: "unavailable" };
  }
  const cents = quantizeHalfUp(aligned.ask - aligned.bid, aligned.scale, 2);
  return {
    state: "ready",
    usd: formatFixed(cents, 2),
    basisPoints: basisPoints(cents, aligned.bid + aligned.ask, aligned.scale),
  };
}

export function spreadLine(bid: string, ask: string): string {
  const spread = quoteSpread(bid, ask);
  if (spread.state === "unavailable") {
    return "Spread is unavailable.";
  }
  return `Spread $${spread.usd} (${spread.basisPoints} bp).`;
}
