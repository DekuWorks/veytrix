import { describe, expect, it } from "vitest";
import { CANDLE_CLOSE_SLACK_SECONDS, candleAge } from "./candleAge";

const NOW = Date.parse("2026-11-08T05:00:00.000Z");

function startBeforeClose(secondsAgo: number): string {
  return new Date(NOW - (60 + secondsAgo) * 1000).toISOString().replace(".000Z", "Z");
}

describe("candle age", () => {
  it("keeps an open bucket current and a recently closed bucket off the stale line", () => {
    expect(CANDLE_CLOSE_SLACK_SECONDS).toBe(90);
    const current = candleAge("2026-11-08T04:59:30Z", NOW);
    expect(current.state).toBe("current");
    expect(current.line).toBe("Current 1-minute candle. 30 seconds left.");
    expect(current.line).not.toContain("stale");

    const closed = candleAge(startBeforeClose(10), NOW);
    expect(closed).toMatchObject({ state: "closed", ageSeconds: 10 });
    expect(closed.line).toBe("Last 1-minute candle closed 10 seconds ago.");
    expect(closed.line).not.toContain("stale");

    const slack = candleAge(startBeforeClose(90), NOW);
    expect(slack.state).toBe("closed");
    expect(slack.line).toBe("Last 1-minute candle closed 90 seconds ago.");
  });

  it("marks a close older than the slack as stale and does not call an unreadable time current", () => {
    const stale = candleAge(startBeforeClose(91), NOW);
    expect(stale).toMatchObject({ state: "stale", ageSeconds: 91 });
    expect(stale.line).toBe("1-minute candle is stale. Age 91 seconds.");
    const unreadable = candleAge("2026-11-08Tnot-readableZ", NOW);
    expect(unreadable).toEqual({ state: "unreadable", line: "Candle time is unreadable." });
    expect(unreadable.line).not.toContain("Current");
  });
});