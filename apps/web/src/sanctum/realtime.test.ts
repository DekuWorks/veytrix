import { beforeEach, describe, expect, it, vi } from "vitest";
import { openSanctumChannel, supabaseBlocked } from "./realtime";

const { createClient } = vi.hoisted(() => ({
  createClient: vi.fn(() => ({
    channel: vi.fn(() => ({
      on: vi.fn().mockReturnThis(),
      subscribe: vi.fn().mockReturnThis(),
    })),
    removeChannel: vi.fn(),
  })),
}));

vi.mock("@supabase/supabase-js", () => ({
  createClient,
}));

function jwt(role: string): string {
  const encode = (value: object) =>
    btoa(JSON.stringify(value)).replace(/=+$/g, "").replace(/\+/g, "-").replace(/\//g, "_");
  return `${encode({ alg: "none" })}.${encode({ role })}.sig`;
}

describe("sanctum realtime", () => {
  beforeEach(() => {
    createClient.mockClear();
  });

  it("polls when Supabase is not configured", async () => {
    const feed = await openSanctumChannel({}, () => undefined);
    expect(feed.mode).toBe("poll");
    expect(createClient).not.toHaveBeenCalled();
  });

  it("refuses a service-role key", async () => {
    expect(supabaseBlocked({ url: "https://example.supabase.co", anonKey: jwt("service_role") })).toBe(
      "service_role",
    );
    const feed = await openSanctumChannel(
      { url: "https://example.supabase.co", anonKey: jwt("service_role") },
      () => undefined,
    );
    expect(feed.mode).toBe("poll");
    expect(createClient).not.toHaveBeenCalled();
  });

  it("subscribes only with an anon key", async () => {
    const feed = await openSanctumChannel(
      { url: "https://example.supabase.co", anonKey: jwt("anon") },
      () => undefined,
    );
    expect(feed.mode).toBe("realtime");
    expect(createClient).toHaveBeenCalledTimes(1);
    feed.close();
  });
});

describe("comms realtime doorbell", () => {
  it("polls when Supabase is not configured and says so", async () => {
    const { openCommsChannel } = await import("./realtime");
    const feed = await openCommsChannel({}, () => undefined);
    expect(feed.mode).toBe("poll");
  });

  it("refuses a service-role key and keeps polling", async () => {
    const { openCommsChannel } = await import("./realtime");
    const feed = await openCommsChannel(
      { url: "https://x.supabase.co", anonKey: jwt("service_role") },
      () => undefined,
    );
    expect(feed.mode).toBe("poll");
  });

  it("subscribes to the comms channel when an anon key is set", async () => {
    const { openCommsChannel } = await import("./realtime");
    createClient.mockClear();
    const feed = await openCommsChannel(
      { url: "https://x.supabase.co", anonKey: jwt("anon") },
      () => undefined,
    );
    expect(feed.mode).toBe("realtime");
    expect(createClient).toHaveBeenCalledTimes(1);
  });
});
