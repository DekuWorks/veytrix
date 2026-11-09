const MINUTE_MS = 60_000;

export const MOVE_AGE_NOTE =
  "Age of this 1-minute move. Not news. Not a trading signal. No order is sent.";

export function moveAgeMinutes(barStart: string, now: number): number | null {
  const start = Date.parse(barStart);
  if (!Number.isFinite(start) || !Number.isFinite(now)) {
    return null;
  }
  const elapsed = now - start;
  if (elapsed < 0) {
    return null;
  }
  return Math.floor(elapsed / MINUTE_MS);
}

export function moveAgeLine(barStart: string, now: number): string {
  const minutes = moveAgeMinutes(barStart, now);
  if (minutes === null) {
    return "Move age is unavailable.";
  }
  const unit = minutes === 1 ? "minute" : "minutes";
  return `Move age ${minutes} ${unit}.`;
}
