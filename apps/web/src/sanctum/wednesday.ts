const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] as const;

export type NewYorkDate = {
  year: number;
  month: number;
  day: number;
  weekday: string;
};

export function newYorkDate(now: Date): NewYorkDate {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    weekday: "short",
  }).formatToParts(now);
  const read = (type: string) => parts.find((part) => part.type === type)?.value ?? "";
  return {
    year: Number(read("year")),
    month: Number(read("month")),
    day: Number(read("day")),
    weekday: read("weekday"),
  };
}

function shiftIso(year: number, month: number, day: number, add: number): string {
  const date = new Date(Date.UTC(year, month - 1, day + add));
  return date.toISOString().slice(0, 10);
}

/** Next Wednesday on the New York calendar, including today when it is Wednesday. */
export function nextWednesday(now: Date): string {
  const today = newYorkDate(now);
  const index = WEEKDAYS.indexOf(today.weekday as (typeof WEEKDAYS)[number]);
  const delta = index < 0 ? 0 : (2 - index + 7) % 7;
  return shiftIso(today.year, today.month, today.day, delta);
}

export function formatLongDate(iso: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!match) {
    return iso;
  }
  const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])));
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(date);
}

export function formatClock(now: Date): string {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
    timeZoneName: "short",
  }).formatToParts(now);
  const read = (type: string) => parts.find((part) => part.type === type)?.value ?? "";
  return `${read("weekday")}, ${read("month")} ${read("day")}, ${read("year")} ${read("hour")}:${read("minute")} ${read("dayPeriod")} ${read("timeZoneName")}`;
}
