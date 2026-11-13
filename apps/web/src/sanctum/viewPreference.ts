/** Last Sanctum camera and rail. Local only. Not a broker setting. */

export const VIEW_STORAGE_KEY = "veytrix.sanctum.view";

export const SHOTS = {
  sky: { scale: 1, x: 0, y: 0 },
  floor: { scale: 1.2, x: 0, y: 10 },
  center: { scale: 1.55, x: 0, y: -10 },
  meeting: { scale: 1.65, x: 0, y: -90 },
  trading: { scale: 1.4, x: 0, y: 20 },
} as const;

export type ShotName = keyof typeof SHOTS;
export type CameraName = ShotName | "custom";
export type RailId =
  | "sky"
  | "floor"
  | "agents"
  | "activity"
  | "boardroom"
  | "cameras"
  | "talk"
  | "logs";

export type Shot = { scale: number; x: number; y: number };

export type SanctumView = {
  rail: RailId;
  camera: CameraName;
  shot: Shot;
};

const RAILS = new Set<string>([
  "sky",
  "floor",
  "agents",
  "activity",
  "boardroom",
  "cameras",
  "talk",
  "logs",
]);

const CAMERAS = new Set<string>(["sky", "floor", "center", "meeting", "trading", "custom"]);

export const SKY_VIEW: SanctumView = {
  rail: "sky",
  camera: "sky",
  shot: { ...SHOTS.sky },
};

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function clampShot(shot: Shot): Shot {
  return {
    scale: clamp(shot.scale, 0.85, 1.8),
    x: clamp(shot.x, -180, 180),
    y: clamp(shot.y, -180, 180),
  };
}

export function readStoredView(raw: string | null): SanctumView {
  if (!raw) {
    return SKY_VIEW;
  }
  try {
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null) {
      return SKY_VIEW;
    }
    const record = parsed as Partial<SanctumView>;
    if (typeof record.rail !== "string" || !RAILS.has(record.rail)) {
      return SKY_VIEW;
    }
    if (typeof record.camera !== "string" || !CAMERAS.has(record.camera)) {
      return SKY_VIEW;
    }
    const shot = record.shot;
    if (
      typeof shot !== "object" ||
      shot === null ||
      typeof shot.scale !== "number" ||
      typeof shot.x !== "number" ||
      typeof shot.y !== "number" ||
      !Number.isFinite(shot.scale) ||
      !Number.isFinite(shot.x) ||
      !Number.isFinite(shot.y)
    ) {
      return SKY_VIEW;
    }
    return {
      rail: record.rail,
      camera: record.camera,
      shot: clampShot(shot),
    };
  } catch {
    return SKY_VIEW;
  }
}

export function loadView(storage: Pick<Storage, "getItem">): SanctumView {
  try {
    return readStoredView(storage.getItem(VIEW_STORAGE_KEY));
  } catch {
    return SKY_VIEW;
  }
}

export function saveView(storage: Pick<Storage, "setItem">, view: SanctumView): void {
  storage.setItem(VIEW_STORAGE_KEY, JSON.stringify(view));
}

/** Full sky shot. This does not change a desk, a permission, or an order. */
export function returnToSky(): SanctumView {
  return {
    rail: "sky",
    camera: "sky",
    shot: { ...SHOTS.sky },
  };
}
