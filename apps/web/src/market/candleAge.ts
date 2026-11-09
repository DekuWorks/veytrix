const BUCKET_MS = 60_000;

// 90 seconds of slack for the ~30s server cache and the ~45s UI refresh.
export const CANDLE_CLOSE_SLACK_SECONDS = 90;

export const CANDLE_AGE_NOTE =
  "Candle time is the Coinbase bucket start. The close is not the live print. No order is sent.";

export type CandleAge =
  | { state: "current"; secondsLeft: number; line: string }
  | { state: "closed"; ageSeconds: number; line: string }
  | { state: "stale"; ageSeconds: number; line: string }
  | { state: "unreadable"; line: string };

function seconds(count: number): string {
  return `${count} ${count === 1 ? "second" : "seconds"}`;
}

export function candleAge(barStart: string, now: number): CandleAge {
  const start = Date.parse(barStart);
  if (!Number.isFinite(start)) {
    return { state: "unreadable", line: "Candle time is unreadable." };
  }
  const close = start + BUCKET_MS;
  if (now < close) {
    const secondsLeft = Math.ceil((close - now) / 1000);
    return {
      state: "current",
      secondsLeft,
      line: `Current 1-minute candle. ${seconds(secondsLeft)} left.`,
    };
  }
  const ageMs = now - close;
  const ageSeconds = Math.floor(ageMs / 1000);
  if (ageMs <= CANDLE_CLOSE_SLACK_SECONDS * 1000) {
    return {
      state: "closed",
      ageSeconds,
      line: `Last 1-minute candle closed ${seconds(ageSeconds)} ago.`,
    };
  }
  return {
    state: "stale",
    ageSeconds,
    line: `1-minute candle is stale. Age ${ageSeconds} seconds.`,
  };
}

export function latestCandleAge(bars: readonly { bar_start: string }[], now: number): CandleAge {
  const latest = bars.at(-1);
  if (latest === undefined) {
    return { state: "unreadable", line: "Candle time is unreadable." };
  }
  return candleAge(latest.bar_start, now);
}
