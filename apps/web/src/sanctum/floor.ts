import { AGENT_CODES, type AgentCode } from "../api/types";

export const COLS = 60;
export const ROWS = 42;
export const TILE = 16;
export const WORLD_W = COLS * TILE;
export const WORLD_H = ROWS * TILE;

export type Tile = { x: number; y: number };

export type PixelRect = { x: number; y: number; w: number; h: number };

type Room = { x0: number; y0: number; x1: number; y1: number };

const HALL: Room = { x0: 8, y0: 2, x1: 51, y1: 29 };
const LEFT_LOUNGE: Room = { x0: 0, y0: 20, x1: 6, y1: 39 };
const LEFT_DOOR: Room = { x0: 7, y0: 22, x1: 7, y1: 25 };
const RIGHT_LOUNGE: Room = { x0: 53, y0: 20, x1: 59, y1: 39 };
const RIGHT_DOOR: Room = { x0: 52, y0: 22, x1: 52, y1: 25 };
const BOARDROOM_ROOM: Room = { x0: 22, y0: 32, x1: 39, y1: 39 };
const BOARD_DOOR: Room = { x0: 28, y0: 30, x1: 32, y1: 31 };

const ROOMS: Room[] = [
  HALL,
  LEFT_LOUNGE,
  LEFT_DOOR,
  RIGHT_LOUNGE,
  RIGHT_DOOR,
  BOARDROOM_ROOM,
  BOARD_DOOR,
];

export const GLOBE: Tile = { x: 30, y: 16 };
export const SIGN: Tile = { x: 30, y: 5 };
export const BOARDROOM: Tile = { x: 30, y: 35 };
export const VISITOR_START: Tile = { x: 4, y: 30 };

export const FLOOR_ORDER = [
  "RESEARCH-01",
  "ETF-01",
  "DEFI-01",
  "CRYPTO-01",
  "STOCK-01",
  "FUTURES-01",
  "RISK-01",
  "DAY-01",
  "TREASURY-01",
  "SUPERVISOR-01",
] as const satisfies readonly AgentCode[];

export const DESK_TILES: Record<AgentCode, Tile> = {
  "RESEARCH-01": { x: 16, y: 11 },
  "ETF-01": { x: 26, y: 9 },
  "DEFI-01": { x: 38, y: 11 },
  "CRYPTO-01": { x: 49, y: 10 },
  "STOCK-01": { x: 16, y: 20 },
  "FUTURES-01": { x: 42, y: 20 },
  "RISK-01": { x: 48, y: 24 },
  "DAY-01": { x: 16, y: 27 },
  "TREASURY-01": { x: 44, y: 27 },
  "SUPERVISOR-01": { x: 30, y: 23 },
};

export const BOARDROOM_SEATS: Record<AgentCode, Tile> = {
  "SUPERVISOR-01": { x: 24, y: 34 },
  "DAY-01": { x: 27, y: 34 },
  "STOCK-01": { x: 30, y: 34 },
  "ETF-01": { x: 33, y: 34 },
  "CRYPTO-01": { x: 36, y: 34 },
  "RESEARCH-01": { x: 24, y: 38 },
  "DEFI-01": { x: 27, y: 38 },
  "RISK-01": { x: 30, y: 38 },
  "TREASURY-01": { x: 33, y: 38 },
  "FUTURES-01": { x: 36, y: 38 },
};

const TRADING_DESKS: AgentCode[] = ["DAY-01", "STOCK-01", "ETF-01", "FUTURES-01", "CRYPTO-01"];

function inRoom(x: number, y: number, room: Room): boolean {
  return x >= room.x0 && x <= room.x1 && y >= room.y0 && y <= room.y1;
}

export function isInterior(x: number, y: number): boolean {
  return ROOMS.some((room) => inRoom(x, y, room));
}

export type FloorZone = "void" | "hall" | "lounge" | "boardroom" | "door";

export function zoneAt(x: number, y: number): FloorZone {
  if (!isInterior(x, y)) {
    return "void";
  }
  if (inRoom(x, y, LEFT_DOOR) || inRoom(x, y, RIGHT_DOOR) || inRoom(x, y, BOARD_DOOR)) {
    return "door";
  }
  if (inRoom(x, y, BOARDROOM_ROOM)) {
    return "boardroom";
  }
  if (inRoom(x, y, LEFT_LOUNGE) || inRoom(x, y, RIGHT_LOUNGE)) {
    return "lounge";
  }
  return "hall";
}

function isDoor(x: number, y: number): boolean {
  return zoneAt(x, y) === "door";
}

export function deskFootprint(code: AgentCode): Tile[] {
  if (code === "SUPERVISOR-01") {
    return [];
  }
  const anchor = DESK_TILES[code];
  const dx = Math.sign(GLOBE.x - anchor.x);
  const dy = Math.sign(GLOBE.y - anchor.y);
  const back = { x: anchor.x - dx, y: anchor.y - dy };
  const side = { x: back.x + (dy === 0 ? 1 : 0), y: back.y + (dx === 0 ? 1 : 0) };
  return [back, side].filter(
    (tile, index, list) =>
      list.findIndex((item) => item.x === tile.x && item.y === tile.y) === index &&
      !(tile.x === anchor.x && tile.y === anchor.y),
  );
}

function inTiles(x: number, y: number, tiles: Tile[]): boolean {
  return tiles.some((tile) => tile.x === x && tile.y === y);
}

const SHELVES: Room[] = [
  { x0: 12, y0: 3, x1: 20, y1: 5 },
  { x0: 40, y0: 3, x1: 48, y1: 5 },
];

const WATER: Room = { x0: 2, y0: 23, x1: 5, y1: 27 };
const SOFA: Room = { x0: 1, y0: 33, x1: 5, y1: 36 };
const TABLE: Room = { x0: 26, y0: 35, x1: 34, y1: 36 };
const ROUND_TABLES: Tile[] = [
  { x: 56, y: 26 },
  { x: 56, y: 33 },
];

export const TREES: Tile[] = [
  { x: 11, y: 5 },
  { x: 48, y: 5 },
];

export const LAMPS: Tile[] = [
  { x: 14, y: 15 },
  { x: 22, y: 18 },
  { x: 36, y: 18 },
  { x: 46, y: 16 },
  { x: 18, y: 26 },
  { x: 40, y: 26 },
];

export const PLANTS: Tile[] = [
  { x: 10, y: 14 },
  { x: 21, y: 13 },
  { x: 34, y: 12 },
  { x: 47, y: 14 },
  { x: 13, y: 24 },
  { x: 50, y: 22 },
  { x: 4, y: 21 },
  { x: 55, y: 22 },
];

function furnitureAt(x: number, y: number): boolean {
  if (Math.max(Math.abs(x - GLOBE.x), Math.abs(y - GLOBE.y)) <= 1) {
    return true;
  }
  if (SHELVES.some((shelf) => inRoom(x, y, shelf))) {
    return true;
  }
  if (inRoom(x, y, WATER) || inRoom(x, y, SOFA) || inRoom(x, y, TABLE)) {
    return true;
  }
  if (inTiles(x, y, ROUND_TABLES)) {
    return true;
  }
  return AGENT_CODES.some((code) => inTiles(x, y, deskFootprint(code)));
}

export function isWalkable(x: number, y: number): boolean {
  if (!isInterior(x, y)) {
    return false;
  }
  if (isDoor(x, y)) {
    return true;
  }
  return !furnitureAt(x, y);
}

export function tileCenter(tile: Tile): { x: number; y: number } {
  return { x: tile.x * TILE + TILE / 2, y: tile.y * TILE + TILE / 2 };
}

export function frameRect(mode: "sky" | "center" | "meeting" | "trading"): PixelRect {
  if (mode === "sky") {
    return { x: 0, y: 0, w: WORLD_W, h: WORLD_H };
  }
  if (mode === "center") {
    return {
      x: (GLOBE.x - 8) * TILE,
      y: (GLOBE.y - 7) * TILE,
      w: 16 * TILE,
      h: 16 * TILE,
    };
  }
  if (mode === "meeting") {
    return { x: 20 * TILE, y: 29 * TILE, w: 22 * TILE, h: 12 * TILE };
  }
  const xs = TRADING_DESKS.map((code) => DESK_TILES[code].x);
  const ys = TRADING_DESKS.map((code) => DESK_TILES[code].y);
  const minX = Math.min(...xs) - 2;
  const maxX = Math.max(...xs) + 2;
  const minY = Math.min(...ys) - 2;
  const maxY = Math.max(...ys) + 2;
  return {
    x: minX * TILE,
    y: minY * TILE,
    w: (maxX - minX + 1) * TILE,
    h: (maxY - minY + 1) * TILE,
  };
}

