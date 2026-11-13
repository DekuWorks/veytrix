import { describe, expect, it } from "vitest";
import { AGENT_CODES, type AgentCode } from "../api/types";
import { activityFeed, paperTradeStat, poseFor, poseFromBroadcast, verifiedTrading } from "./activity";
import {
  BOARDROOM_SEATS,
  DESK_TILES,
  FLOOR_ORDER,
  frameRect,
  isWalkable,
} from "./floor";
import { findPath } from "./pathfinding";
import { renderAgent } from "./sprites";
import { nextWednesday } from "./wednesday";

const desk = {
  code: "DAY-01" as const,
  display_name: "Day desk",
  desk: "equities-session",
  status: "disabled" as const,
  paper_only: true as const,
  can_submit_orders: false as const,
  can_sign: false as const,
  can_transfer_funds: false as const,
  holds_credentials: false as const,
  permission_effect: "deny" as const,
};

describe("sanctum floor", () => {
  it("places every registry desk on a walkable tile that can reach the boardroom", () => {
    expect(new Set(FLOOR_ORDER)).toEqual(new Set(AGENT_CODES));
    for (const code of AGENT_CODES) {
      const home = DESK_TILES[code];
      const seat = BOARDROOM_SEATS[code];
      expect(isWalkable(home.x, home.y)).toBe(true);
      expect(isWalkable(seat.x, seat.y)).toBe(true);
      const path = findPath(home, seat, isWalkable);
      expect(path.length).toBeGreaterThan(1);
      expect(path.every((tile) => isWalkable(tile.x, tile.y))).toBe(true);
    }
  });

  it("frames the trading desks without leaving the floor", () => {
    const frame = frameRect("trading");
    expect(frame.w).toBeGreaterThan(0);
    expect(frame.h).toBeGreaterThan(0);
    for (const code of ["DAY-01", "STOCK-01", "ETF-01", "FUTURES-01", "CRYPTO-01"] as AgentCode[]) {
      const tile = DESK_TILES[code];
      expect(tile.x * 16).toBeGreaterThanOrEqual(frame.x);
      expect(tile.y * 16).toBeGreaterThanOrEqual(frame.y);
    }
  });
});

describe("sanctum poses", () => {
  it("keeps a denied desk idle and treats a failed read as an error", () => {
    expect(poseFor(desk, true)).toBe("idle");
    expect(poseFor({ ...desk, status: "enabled" }, true)).toBe("idle");
    expect(poseFromBroadcast({
      code: "DAY-01",
      status: "enabled",
      execution_permitted: false,
      trading_rights: "denied",
    })?.pose).toBe("idle");
    expect(poseFor(desk, false)).toBe("error");
    expect(poseFor(undefined, true)).toBe("error");
  });

  it("does not treat a permitted execution flag as work", () => {
    expect(
      poseFromBroadcast({
        payload: {
          code: "FUTURES-01",
          status: "disabled",
          trading_rights: "denied",
          execution_permitted: true,
          order_submitted: false,
          running: true,
        },
      }),
    ).toEqual({ code: "FUTURES-01", pose: "error" });
  });
});

describe("sanctum activity copy", () => {
  it("says none verified unless a row is broker-confirmed", () => {
    expect(verifiedTrading({ broker_read: "absent", reconciled: false, local_orders: 0, rows: [] })).toBe(
      "none verified",
    );
    expect(
      verifiedTrading({
        broker_read: "absent",
        reconciled: false,
        local_orders: 1,
        rows: [{ broker_status: "broker_confirmed" }],
      }),
    ).toBe("broker-confirmed");
    expect(paperTradeStat({ broker_read: "absent", reconciled: false, local_orders: 0, rows: [] }).value).toBe("0");
  });

  it("does not invent tasks, trades, or a Topstep review", () => {
    const lines = activityFeed({
      agents: [{ code: "FUTURES-01", status: "disabled" }],
      futuresNote: "FUTURES-01 is disabled. Topstep automation is off.",
      audit: [],
    });
    const text = lines.join(" ");
    expect(text).toContain("Activity is not verified");
    expect(text).toContain("none verified");
    expect(text).not.toContain("Operational");
    expect(text).not.toContain("reviewing Topstep");
    expect(text).not.toContain("24");
  });
});

describe("sanctum wednesday", () => {
  it("uses the next Wednesday and keeps a Wednesday on that day", () => {
    expect(nextWednesday(new Date("2026-11-09T16:00:00Z"))).toBe("2026-11-11");
    expect(nextWednesday(new Date("2026-11-11T16:00:00Z"))).toBe("2026-11-11");
    expect(nextWednesday(new Date("2026-11-12T16:00:00Z"))).toBe("2026-11-18");
  });
});

describe("sanctum sprites", () => {
  it("draws distinct people", () => {
    const crypto = renderAgent("CRYPTO-01", "sit", 0);
    const risk = renderAgent("RISK-01", "sit", 0);
    expect(Array.from(crypto.data)).not.toEqual(Array.from(risk.data));
    expect(crypto.data.includes(226)).toBe(false);
    expect(renderAgent("SUPERVISOR-01", "sit", 0).data.includes(226)).toBe(true);
  });
});
