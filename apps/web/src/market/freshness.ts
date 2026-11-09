const EXCHANGE_TIME = /^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d+))?Z$/;

export const STALE_AFTER_MS = 20_000;

export function parseExchangeTime(value: string): number | null {
  const match = EXCHANGE_TIME.exec(value);
  if (match === null) {
    return null;
  }
  const fraction = match[2];
  const iso =
    fraction === undefined ? `${match[1]}Z` : `${match[1]}.${fraction.slice(0, 3).padEnd(3, "0")}Z`;
  const parsed = Date.parse(iso);
  return Number.isNaN(parsed) ? null : parsed;
}

export type PrintStatus =
  | { state: "current" }
  | { state: "stale"; ageSeconds: number; line: string }
  | { state: "unreadable"; line: string };

export function printStatus(tradeTime: string, now: number): PrintStatus {
  const parsed = parseExchangeTime(tradeTime);
  if (parsed === null) {
    return { state: "unreadable", line: "Exchange time is unreadable." };
  }
  const ageMs = now - parsed;
  if (ageMs > STALE_AFTER_MS) {
    const ageSeconds = Math.floor(ageMs / 1000);
    return { state: "stale", ageSeconds, line: `Print is stale. Age ${ageSeconds} seconds.` };
  }
  return { state: "current" };
}
