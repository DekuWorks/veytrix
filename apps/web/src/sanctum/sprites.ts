import type { AgentCode } from "../api/types";
import {
  BOARDROOM,
  COLS,
  DESK_TILES,
  GLOBE,
  LAMPS,
  PLANTS,
  ROWS,
  SIGN,
  TILE,
  TREES,
  isInterior,
  zoneAt,
  type Tile,
} from "./floor";

export class Pix {
  readonly data: Uint8ClampedArray;

  constructor(
    readonly width: number,
    readonly height: number,
  ) {
    this.data = new Uint8ClampedArray(width * height * 4);
  }

  set(x: number, y: number, color: string) {
    const px = Math.round(x);
    const py = Math.round(y);
    if (px < 0 || py < 0 || px >= this.width || py >= this.height) {
      return;
    }
    const parsed = parseColor(color);
    const index = (py * this.width + px) * 4;
    const alpha = parsed.a / 255;
    this.data[index] = Math.round(parsed.r * alpha + this.data[index] * (1 - alpha));
    this.data[index + 1] = Math.round(parsed.g * alpha + this.data[index + 1] * (1 - alpha));
    this.data[index + 2] = Math.round(parsed.b * alpha + this.data[index + 2] * (1 - alpha));
    this.data[index + 3] = 255;
  }

  fillRect(x: number, y: number, w: number, h: number, color: string) {
    for (let py = 0; py < h; py += 1) {
      for (let px = 0; px < w; px += 1) {
        this.set(x + px, y + py, color);
      }
    }
  }

  fillCircle(cx: number, cy: number, radius: number, color: string) {
    const r = Math.ceil(radius);
    for (let y = -r; y <= r; y += 1) {
      for (let x = -r; x <= r; x += 1) {
        if (x * x + y * y <= radius * radius) {
          this.set(cx + x, cy + y, color);
        }
      }
    }
  }
}

function parseColor(color: string): { r: number; g: number; b: number; a: number } {
  const hex = color.replace("#", "");
  const value = hex.length <= 4 ? hex.replace(/./g, (char) => char + char) : hex;
  return {
    r: Number.parseInt(value.slice(0, 2), 16),
    g: Number.parseInt(value.slice(2, 4), 16),
    b: Number.parseInt(value.slice(4, 6), 16),
    a: value.length >= 8 ? Number.parseInt(value.slice(6, 8), 16) : 255,
  };
}

function shade(x: number, y: number, base: [number, number, number]): string {
  const shift = ((x * 13 + y * 7) % 5) - 2;
  const channel = (value: number) => Math.max(0, Math.min(255, value + shift)).toString(16).padStart(2, "0");
  return `#${channel(base[0])}${channel(base[1])}${channel(base[2])}`;
}

function touchesInterior(x: number, y: number): boolean {
  for (let dy = -1; dy <= 1; dy += 1) {
    for (let dx = -1; dx <= 1; dx += 1) {
      if ((dx !== 0 || dy !== 0) && isInterior(x + dx, y + dy)) {
        return true;
      }
    }
  }
  return false;
}

function paintStone(pix: Pix) {
  for (let y = 0; y < ROWS; y += 1) {
    for (let x = 0; x < COLS; x += 1) {
      const zone = zoneAt(x, y);
      if (zone === "void") {
        if (touchesInterior(x, y)) {
          pix.fillRect(x * TILE, y * TILE, TILE, TILE, "#101614");
        }
        continue;
      }
      const base: [number, number, number] =
        zone === "boardroom" ? [22, 36, 38] : zone === "lounge" ? [42, 36, 28] : [32, 40, 36];
      for (let py = 0; py < TILE; py += 1) {
        for (let px = 0; px < TILE; px += 1) {
          const grout = (x % 2 === 0 && px === 0) || (y % 2 === 0 && py === 0);
          const speck = (x * 3 + px + y * 5 + py) % 17 === 0;
          pix.set(
            x * TILE + px,
            y * TILE + py,
            grout ? "#1a2420" : speck ? "#3e5248" : shade(x, y, base),
          );
        }
      }
      if (x === GLOBE.x && y >= SIGN.y && y <= DESK_TILES["SUPERVISOR-01"].y) {
        pix.fillRect(x * TILE + 6, y * TILE, 4, TILE, "#14382c");
      }
    }
  }
  for (let y = 0; y < ROWS; y += 1) {
    for (let x = 0; x < COLS; x += 1) {
      if (isInterior(x, y)) {
        continue;
      }
      const originX = x * TILE;
      const originY = y * TILE;
      if (isInterior(x, y + 1)) {
        pix.fillRect(originX, originY + TILE - 2, TILE, 2, "#3dbe8b");
      }
      if (isInterior(x, y - 1)) {
        pix.fillRect(originX, originY, TILE, 2, "#3dbe8b");
      }
      if (isInterior(x + 1, y)) {
        pix.fillRect(originX + TILE - 2, originY, 2, TILE, "#3dbe8b");
      }
      if (isInterior(x - 1, y)) {
        pix.fillRect(originX, originY, 2, TILE, "#3dbe8b");
      }
    }
  }
}

function paintTree(pix: Pix, tile: Tile) {
  const cx = tile.x * TILE + 8;
  const cy = tile.y * TILE + 8;
  pix.fillRect(cx - 2, cy, 4, 22, "#3a2a1c");
  pix.fillCircle(cx, cy - 8, 22, "#4a2068");
  pix.fillCircle(cx - 14, cy - 2, 16, "#6b348c");
  pix.fillCircle(cx + 12, cy - 10, 14, "#8a4aaa");
  pix.fillCircle(cx + 2, cy - 14, 8, "#b07ad0");
}

function paintShelf(pix: Pix, x: number, y: number, w: number) {
  pix.fillRect(x, y, w, 28, "#3a2c22");
  const books = ["#6b3a4a", "#2a4a6a", "#3d6b4a", "#6a5a2a", "#4a3a6a"];
  for (let px = 2; px < w - 2; px += 3) {
    pix.fillRect(x + px, y + 3, 2, 8, books[px % books.length]);
    pix.fillRect(x + px, y + 14, 2, 8, books[(px + 2) % books.length]);
  }
}

function paintSign(pix: Pix) {
  const x = SIGN.x * TILE - 40;
  const y = SIGN.y * TILE - 18;
  pix.fillRect(x, y, 96, 52, "#0c1411");
  pix.fillRect(x, y, 96, 2, "#3dbe8b");
  pix.fillRect(x, y + 50, 96, 2, "#3dbe8b");
  pix.fillRect(x, y, 2, 52, "#3dbe8b");
  pix.fillRect(x + 94, y, 2, 52, "#3dbe8b");
  for (let i = 0; i < 14; i += 1) {
    pix.fillRect(x + 40 - i, y + 8 + i, 2, 2, "#b8ffd8");
    pix.fillRect(x + 54 + i, y + 8 + i, 2, 2, "#b8ffd8");
  }
}

function paintGlobe(pix: Pix) {
  const cx = GLOBE.x * TILE + TILE / 2;
  const cy = GLOBE.y * TILE + TILE / 2;
  const points = Array.from({ length: 6 }, (_, index) => {
    const angle = -Math.PI / 2 + index * (Math.PI / 3);
    return { x: cx + Math.cos(angle) * 62, y: cy + Math.sin(angle) * 62 };
  });
  const ys = points.map((point) => point.y);
  const minY = Math.floor(Math.min(...ys));
  const maxY = Math.ceil(Math.max(...ys));
  for (let y = minY; y <= maxY; y += 1) {
    const xs: number[] = [];
    for (let index = 0; index < points.length; index += 1) {
      const start = points[index];
      const end = points[(index + 1) % points.length];
      if ((start.y <= y && end.y > y) || (end.y <= y && start.y > y)) {
        const t = (y - start.y) / (end.y - start.y);
        xs.push(start.x + t * (end.x - start.x));
      }
    }
    xs.sort((left, right) => left - right);
    for (let index = 0; index + 1 < xs.length; index += 2) {
      for (let x = Math.ceil(xs[index]); x <= Math.floor(xs[index + 1]); x += 1) {
        pix.set(x, y, "#10241c");
      }
    }
  }
  pix.fillCircle(cx, cy, 54, "#14382c66");
  pix.fillCircle(cx, cy, 36, "#0e3d30");
  pix.fillCircle(cx, cy, 26, "#1f9a62");
  pix.fillCircle(cx, cy, 14, "#8dffc0");
  pix.fillCircle(cx - 8, cy - 4, 6, "#0c3a2c");
  pix.fillCircle(cx + 7, cy + 5, 4, "#d8fff0");
}

const SCREENS: Record<AgentCode, string> = {
  "RESEARCH-01": "#8a6bb8",
  "ETF-01": "#3dbe8b",
  "DEFI-01": "#3a8ab8",
  "CRYPTO-01": "#7a5ae0",
  "STOCK-01": "#3dbe8b",
  "FUTURES-01": "#d4b15a",
  "RISK-01": "#c46a6a",
  "DAY-01": "#8ee0b8",
  "TREASURY-01": "#d4b15a",
  "SUPERVISOR-01": "#3dbe8b",
};

function paintDesk(pix: Pix, code: AgentCode) {
  if (code === "SUPERVISOR-01") {
    return;
  }
  const anchor = DESK_TILES[code];
  const dx = Math.sign(GLOBE.x - anchor.x);
  const dy = Math.sign(GLOBE.y - anchor.y);
  const x = anchor.x * TILE - dx * 28 - 8;
  const y = anchor.y * TILE - dy * 22 - 4;
  pix.fillRect(x, y, 40, 22, "#101816");
  pix.fillRect(x + 2, y + 2, 11, 9, SCREENS[code]);
  pix.fillRect(x + 14, y + 2, 11, 9, "#0e2420");
  pix.fillRect(x + 26, y + 2, 11, 9, SCREENS[code]);
  pix.fillRect(x + 4, y + 4, 7, 4, "#d8fff0aa");
}

function paintBoardroom(pix: Pix) {
  const x = (BOARDROOM.x - 4) * TILE;
  const y = (BOARDROOM.y - 1) * TILE;
  pix.fillRect(x, y, 9 * TILE, 28, "#241c14");
  pix.fillRect(x + 8, y + 6, 9 * TILE - 16, 8, "#3a3228");
  for (let seat = 0; seat < 6; seat += 1) {
    pix.fillRect(x + 10 + seat * 20, y - 4, 8, 6, "#4a4034");
    pix.fillRect(x + 10 + seat * 20, y + 28, 8, 6, "#4a4034");
  }
  const cx = BOARDROOM.x * TILE + 8;
  const cy = BOARDROOM.y * TILE + 8;
  for (let i = 0; i < 8; i += 1) {
    pix.fillRect(cx - i, cy - 6 + i, 2, 2, "#3dbe8b");
    pix.fillRect(cx + i, cy - 6 + i, 2, 2, "#3dbe8b");
  }
}

function paintLounge(pix: Pix) {
  pix.fillRect(2 * TILE, 23 * TILE, 4 * TILE, 5 * TILE, "#143848");
  for (let i = 0; i < 5; i += 1) {
    pix.fillRect(2 * TILE + 4, 23 * TILE + 6 + i * 12, 28, 2, "#2a6a80");
  }
  pix.fillRect(1 * TILE, 33 * TILE, 36, 16, "#6a5344");
  pix.fillRect(1 * TILE + 3, 33 * TILE + 3, 30, 8, "#c4b49a");
  pix.fillRect(1 * TILE, 36 * TILE, 28, 14, "#5a4638");
  pix.fillRect(1 * TILE + 4, 36 * TILE + 3, 18, 7, "#a89078");
  for (const table of [
    { x: 56, y: 26 },
    { x: 56, y: 33 },
  ] satisfies Tile[]) {
    const cx = table.x * TILE + 8;
    const cy = table.y * TILE + 8;
    pix.fillCircle(cx, cy, 12, "#3a3228");
    pix.fillCircle(cx, cy, 7, "#5a4c3c");
    pix.fillRect(cx - 16, cy - 3, 6, 6, "#4a4034");
    pix.fillRect(cx + 10, cy - 3, 6, 6, "#4a4034");
  }
}

export function renderFloor(): Pix {
  const pix = new Pix(COLS * TILE, ROWS * TILE);
  pix.fillRect(0, 0, pix.width, pix.height, "#070c0a");
  paintStone(pix);
  paintShelf(pix, 12 * TILE, 3 * TILE, 8 * TILE);
  paintShelf(pix, 40 * TILE, 3 * TILE, 8 * TILE);
  paintSign(pix);
  paintGlobe(pix);
  for (const code of Object.keys(DESK_TILES) as AgentCode[]) {
    paintDesk(pix, code);
  }
  paintBoardroom(pix);
  paintLounge(pix);
  for (const tree of TREES) {
    paintTree(pix, tree);
  }
  for (const lamp of LAMPS) {
    const x = lamp.x * TILE;
    const y = lamp.y * TILE;
    pix.fillRect(x + 6, y, 3, 14, "#2c2a24");
    pix.fillRect(x + 3, y - 2, 9, 4, "#e6c36a");
    pix.fillCircle(x + 7, y, 6, "#f0d48a55");
  }
  for (const plant of PLANTS) {
    const x = plant.x * TILE;
    const y = plant.y * TILE;
    pix.fillRect(x + 4, y + 8, 8, 6, "#5a4030");
    pix.fillCircle(x + 8, y + 5, 6, "#1f6b40");
    pix.fillCircle(x + 5, y + 3, 3, "#3dbe8b");
  }
  return pix;
}

type Look = {
  hair: string;
  skin: string;
  shirt: string;
  legs: string;
  extra: "crown" | "short" | "side" | "antenna" | "bun" | "hood" | "glasses" | "tall" | "badge" | "visor";
};

const LOOKS: Record<AgentCode, Look> = {
  "SUPERVISOR-01": { hair: "#1a1a1a", skin: "#e0b090", shirt: "#12382c", legs: "#0e1a16", extra: "crown" },
  "DAY-01": { hair: "#3a2a22", skin: "#f0c8a0", shirt: "#1c3d32", legs: "#141414", extra: "short" },
  "STOCK-01": { hair: "#222222", skin: "#c89870", shirt: "#243044", legs: "#1a1a1a", extra: "side" },
  "CRYPTO-01": { hair: "#d8c15a", skin: "#e8b896", shirt: "#3a2460", legs: "#1a1028", extra: "antenna" },
  "ETF-01": { hair: "#4a3020", skin: "#e0b090", shirt: "#1e4a38", legs: "#102018", extra: "bun" },
  "DEFI-01": { hair: "#111418", skin: "#d0a080", shirt: "#16485a", legs: "#101418", extra: "hood" },
  "RESEARCH-01": { hair: "#5a4030", skin: "#e8c0a0", shirt: "#6a4030", legs: "#2a2018", extra: "glasses" },
  "RISK-01": { hair: "#2a2a2a", skin: "#c8a080", shirt: "#6a2428", legs: "#1a1010", extra: "tall" },
  "TREASURY-01": { hair: "#6a5428", skin: "#e0b890", shirt: "#8a6a32", legs: "#2a2418", extra: "badge" },
  "FUTURES-01": { hair: "#202428", skin: "#d8b098", shirt: "#2a3848", legs: "#141820", extra: "visor" },
};

export type SpritePose = "sit" | "walk" | "work" | "talk";

export function renderAgent(code: AgentCode, pose: SpritePose, frame: number): Pix {
  const pix = new Pix(16, 24);
  const look = LOOKS[code];
  const bob = pose === "walk" && frame === 1 ? 1 : 0;
  const y0 = (pose === "sit" ? 5 : 2) + bob;
  pix.fillRect(4, 22, 8, 1, "#00000066");
  if (look.extra === "crown") {
    pix.fillRect(4, y0 - 3, 8, 2, "#e2c15a");
    pix.set(4, y0 - 4, "#e2c15a");
    pix.set(7, y0 - 4, "#e2c15a");
    pix.set(11, y0 - 4, "#e2c15a");
  }
  if (look.extra === "tall") {
    pix.fillRect(4, y0 - 2, 8, 2, look.hair);
  }
  if (look.extra === "antenna") {
    pix.set(8, y0 - 2, look.hair);
    pix.set(8, y0 - 1, "#7dffa8");
  }
  pix.fillRect(4, y0, 8, 4, look.hair);
  if (look.extra === "bun") {
    pix.fillRect(11, y0 + 1, 3, 3, look.hair);
  }
  if (look.extra === "hood") {
    pix.fillRect(3, y0, 10, 3, "#102028");
  }
  pix.fillRect(5, y0 + 3, 6, 3, look.skin);
  pix.set(6, y0 + 4, "#1a1a1a");
  pix.set(9, y0 + 4, "#1a1a1a");
  if (look.extra === "glasses") {
    pix.set(6, y0 + 4, "#9fd8ff");
    pix.set(9, y0 + 4, "#9fd8ff");
  }
  if (look.extra === "visor") {
    pix.fillRect(5, y0 + 3, 6, 1, "#7ec8ff");
  }
  if (pose === "talk" && frame === 1) {
    pix.set(7, y0 + 5, "#7a3040");
    pix.set(8, y0 + 5, "#7a3040");
  }
  pix.fillRect(4, y0 + 6, 8, 5, look.shirt);
  if (look.extra === "badge") {
    pix.set(8, y0 + 8, "#f0d48a");
  }
  if (pose === "work") {
    pix.fillRect(frame === 0 ? 12 : 13, y0 + 7, 3, 2, look.skin);
  }
  if (pose === "sit") {
    pix.fillRect(3, y0 + 11, 10, 3, look.legs);
  } else if (pose === "walk" && frame === 1) {
    pix.fillRect(4, y0 + 11, 3, 5, look.legs);
    pix.fillRect(9, y0 + 12, 3, 4, look.legs);
  } else {
    pix.fillRect(5, y0 + 11, 2, 5, look.legs);
    pix.fillRect(9, y0 + 11, 2, 5, look.legs);
  }
  return pix;
}

export function renderVisitor(frame: number): Pix {
  const pix = new Pix(16, 24);
  const y0 = frame === 1 ? 3 : 2;
  pix.fillRect(5, y0, 6, 3, "#e7f3ec");
  pix.fillRect(4, y0 + 4, 8, 6, "#3dbe8b");
  pix.fillRect(5, y0 + 10, 2, 5, "#102018");
  pix.fillRect(9, y0 + 10, 2, frame === 1 ? 4 : 5, "#102018");
  return pix;
}

export function pixToCanvas(pix: Pix): HTMLCanvasElement {
  const canvas = document.createElement("canvas");
  canvas.width = pix.width;
  canvas.height = pix.height;
  const context = canvas.getContext("2d");
  if (!context) {
    return canvas;
  }
  context.putImageData(new ImageData(new Uint8ClampedArray(pix.data), pix.width, pix.height), 0, 0);
  return canvas;
}
