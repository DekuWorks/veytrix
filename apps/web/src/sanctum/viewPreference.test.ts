import { describe, expect, it } from "vitest";
import {
  SHOTS,
  SKY_VIEW,
  VIEW_STORAGE_KEY,
  loadView,
  readStoredView,
  returnToSky,
  saveView,
} from "./viewPreference";

function memory(): Storage {
  const bag = new Map<string, string>();
  return {
    get length() {
      return bag.size;
    },
    clear: () => bag.clear(),
    getItem: (key) => bag.get(key) ?? null,
    key: (index) => [...bag.keys()][index] ?? null,
    removeItem: (key) => bag.delete(key),
    setItem: (key, value) => bag.set(key, value),
  };
}

describe("sanctum view preference", () => {
  it("restores the last rail, camera, and shot", () => {
    const storage = memory();
    const meeting = {
      rail: "boardroom" as const,
      camera: "meeting" as const,
      shot: { ...SHOTS.meeting },
    };
    saveView(storage, meeting);

    expect(storage.getItem(VIEW_STORAGE_KEY)).toContain("boardroom");
    expect(loadView(storage)).toEqual(meeting);
  });

  it("keeps a custom pan inside the floor bounds", () => {
    const stored = readStoredView(
      JSON.stringify({
        rail: "floor",
        camera: "custom",
        shot: { scale: 9, x: 400, y: -400 },
      }),
    );

    expect(stored.rail).toBe("floor");
    expect(stored.camera).toBe("custom");
    expect(stored.shot).toEqual({ scale: 1.8, x: 180, y: -180 });
  });

  it("falls back to the sky view when storage is empty or broken", () => {
    expect(readStoredView(null)).toEqual(SKY_VIEW);
    expect(readStoredView("not-json")).toEqual(SKY_VIEW);
    expect(readStoredView(JSON.stringify({ rail: "vault", camera: "sky", shot: SHOTS.sky }))).toEqual(
      SKY_VIEW,
    );
    const storage = memory();
    storage.getItem = () => {
      throw new Error("blocked");
    };
    expect(loadView(storage)).toEqual(SKY_VIEW);
  });

  it("returns to the full sky view from any saved choice", () => {
    const back = returnToSky();

    expect(back).toEqual(SKY_VIEW);
    expect(back.shot).toEqual({ scale: 1, x: 0, y: 0 });
    expect(back).not.toEqual({
      rail: "boardroom",
      camera: "meeting",
      shot: { ...SHOTS.meeting },
    });
  });
});
