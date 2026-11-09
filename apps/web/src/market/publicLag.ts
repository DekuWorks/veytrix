const MINUTE_MS = 60_000;

export const PUBLIC_LAG_NOTE =
  "First public time minus the event time. Not news. Not a trading signal. No order is sent.";

export function publicLagMinutes(eventTime: string, firstPublicAt: string): number | null {
  const eventMs = Date.parse(eventTime);
  const publicMs = Date.parse(firstPublicAt);
  if (!Number.isFinite(eventMs) || !Number.isFinite(publicMs)) {
    return null;
  }
  return Math.trunc((publicMs - eventMs) / MINUTE_MS);
}

export function publicLagLine(eventTime: string, firstPublicAt: string): string {
  const minutes = publicLagMinutes(eventTime, firstPublicAt);
  if (minutes === null) {
    return "Public lag is unavailable.";
  }
  const unit = minutes === 1 || minutes === -1 ? "minute" : "minutes";
  return `Public lag ${minutes} ${unit}.`;
}
