import Phaser from "phaser";
import type { AgentCode } from "../api/types";
import type { DeskPose } from "./activity";
import {
  BOARDROOM,
  BOARDROOM_SEATS,
  DESK_TILES,
  FLOOR_ORDER,
  SIGN,
  TILE,
  VISITOR_START,
  WORLD_H,
  WORLD_W,
  frameRect,
  isWalkable,
  tileCenter,
  type Tile,
} from "./floor";
import { findPath } from "./pathfinding";
import { pixToCanvas, renderAgent, renderFloor, renderVisitor, type SpritePose } from "./sprites";

export type SanctumMode = "sky" | "floor" | "center" | "meeting" | "trading";

export type SanctumController = {
  destroy: () => void;
  setMode: (mode: SanctumMode) => void;
  panBy: (dx: number, dy: number) => void;
  zoomBy: (factor: number) => void;
  fit: () => void;
  follow: (code: AgentCode | null) => void;
  setPoses: (poses: Partial<Record<AgentCode, DeskPose>>) => void;
  gather: () => void;
  returnToDesks: () => void;
};

type Hooks = {
  onSelect: (code: AgentCode) => void;
};

type Bridge = {
  scene: HqScene | null;
  hooks: Hooks;
  poses: Partial<Record<AgentCode, DeskPose>>;
  pendingMode: SanctumMode | null;
};

type Npc = {
  code: AgentCode;
  sprite: Phaser.GameObjects.Sprite;
  label: Phaser.GameObjects.Text;
  dot: Phaser.GameObjects.Arc;
  crown: Phaser.GameObjects.Graphics | null;
  home: Tile;
  tile: Tile;
  path: Tile[];
  pose: DeskPose;
  gathered: boolean;
};

const POSES: SpritePose[] = ["sit", "walk", "work", "talk"];

class HqScene extends Phaser.Scene {
  private bridge!: Bridge;
  private npcs = new Map<AgentCode, Npc>();
  private player!: Phaser.GameObjects.Sprite;
  private mode: SanctumMode | "pan" = "sky";
  private followCode: AgentCode | null = null;
  private keys?: {
    up: Phaser.Input.Keyboard.Key;
    down: Phaser.Input.Keyboard.Key;
    left: Phaser.Input.Keyboard.Key;
    right: Phaser.Input.Keyboard.Key;
    w: Phaser.Input.Keyboard.Key;
    a: Phaser.Input.Keyboard.Key;
    s: Phaser.Input.Keyboard.Key;
    d: Phaser.Input.Keyboard.Key;
  };
  private dragging = false;
  private lastX = 0;
  private lastY = 0;
  private frame = 0;
  private elapsed = 0;

  constructor() {
    super("hq");
  }

  init(data: { bridge: Bridge }) {
    this.bridge = data.bridge;
    this.bridge.scene = this;
  }

  create() {
    try {
      this.buildFloor();
    } catch (error) {
      const message = error instanceof Error ? (error.stack ?? error.message) : String(error);
      const note = document.createElement("pre");
      note.id = "sanctum-floor-error";
      note.textContent = message;
      note.style.cssText = "position:absolute;inset:8px;z-index:5;color:#f0a8a8;white-space:pre-wrap;font-size:12px";
      this.game.canvas.parentElement?.appendChild(note);
    }
  }

  private buildFloor() {
    const floor = this.add.image(0, 0, this.floorTexture()).setOrigin(0, 0);
    floor.setDepth(0);
    this.makeActors();
    this.makeLabels();
    const camera = this.cameras.main;
    camera.setBounds(0, 0, WORLD_W, WORLD_H);
    camera.setBackgroundColor("#070c0a");
    this.bindInput();
    this.applyMode(this.bridge.pendingMode ?? "sky");
    this.bridge.pendingMode = null;
    this.applyPoses();
    this.scale.on("resize", () => {
      if (this.mode === "sky") {
        this.applyMode("sky");
      }
    });
  }

  update(_time: number, delta: number) {
    this.moveNpcs(delta);
    this.movePlayer(delta);
    this.elapsed += delta;
    if (this.elapsed < 280) {
      return;
    }
    this.elapsed = 0;
    this.frame ^= 1;
    for (const npc of this.npcs.values()) {
      npc.sprite.setTexture(`${npc.code}-${this.visual(npc)}-${this.frame}`);
      this.placeLabel(npc);
    }
    if (this.player.visible) {
      this.player.setTexture(`visitor-${this.frame}`);
    }
  }

  applyMode(mode: SanctumMode) {
    const camera = this.cameras.main;
    this.mode = mode;
    if (mode === "floor") {
      this.player.setVisible(true);
      camera.setZoom(2.1);
      const sprite = this.followCode ? this.npcs.get(this.followCode)?.sprite : this.player;
      camera.startFollow(sprite ?? this.player, true, 0.12, 0.12);
      return;
    }
    this.player.setVisible(false);
    camera.stopFollow();
    const rect = frameRect(mode === "sky" ? "sky" : mode);
    const viewW = this.scale.width;
    const viewH = this.scale.height;
    if (viewW < 20 || viewH < 20) {
      return;
    }
    const zoom = Math.min(viewW / rect.w, viewH / rect.h) * (mode === "sky" ? 0.96 : 0.9);
    camera.setZoom(Phaser.Math.Clamp(zoom, 0.2, 3.5));
    camera.centerOn(rect.x + rect.w / 2, rect.y + rect.h / 2);
  }

  panBy(dx: number, dy: number) {
    const camera = this.cameras.main;
    camera.stopFollow();
    this.mode = "pan";
    this.player.setVisible(false);
    camera.scrollX += dx / camera.zoom;
    camera.scrollY += dy / camera.zoom;
  }

  zoomBy(factor: number) {
    const camera = this.cameras.main;
    camera.setZoom(Phaser.Math.Clamp(camera.zoom * factor, 0.35, 3.5));
  }

  follow(code: AgentCode | null) {
    this.followCode = code;
    if (this.mode === "floor") {
      this.applyMode("floor");
    }
  }

  applyPoses() {
    for (const npc of this.npcs.values()) {
      npc.pose = this.bridge.poses[npc.code] ?? "idle";
      npc.sprite.setTint(npc.pose === "error" ? 0xff9a9a : 0xffffff);
      npc.dot.setFillStyle(npc.pose === "error" ? 0xf0a8a8 : 0x3dbe8b);
    }
  }

  gather() {
    for (const npc of this.npcs.values()) {
      this.walk(npc, BOARDROOM_SEATS[npc.code], true);
    }
  }

  returnToDesks() {
    for (const npc of this.npcs.values()) {
      this.walk(npc, npc.home, false);
    }
  }

  private floorTexture(): string {
    const key = "sanctum-floor";
    if (!this.textures.exists(key)) {
      this.textures.addCanvas(key, pixToCanvas(renderFloor()));
    }
    return key;
  }

  private makeActors() {
    for (const pose of POSES) {
      for (const frame of [0, 1]) {
        for (const code of FLOOR_ORDER) {
          const texture = `${code}-${pose}-${frame}`;
          if (!this.textures.exists(texture)) {
            this.textures.addCanvas(texture, pixToCanvas(renderAgent(code, pose, frame)));
          }
        }
        const visitor = `visitor-${frame}`;
        if (!this.textures.exists(visitor)) {
          this.textures.addCanvas(visitor, pixToCanvas(renderVisitor(frame)));
        }
      }
    }
    for (const code of FLOOR_ORDER) {
      const home = DESK_TILES[code];
      const point = tileCenter(home);
      const sprite = this.add.sprite(point.x, point.y, `${code}-sit-0`).setOrigin(0.5, 0.92).setScale(2.15).setDepth(point.y);
      sprite.setInteractive({ useHandCursor: true });
      sprite.on("pointerdown", (pointer: Phaser.Input.Pointer) => {
        pointer.event?.stopPropagation();
        this.bridge.hooks.onSelect(code);
        if (this.mode === "floor") {
          this.follow(code);
        }
      });
      const label = this.add
        .text(point.x, point.y - 78, code, {
          fontFamily: "IBM Plex Sans, sans-serif",
          fontSize: "15px",
          color: "#7dffa8",
          fontStyle: "600",
        })
        .setOrigin(0.5, 1)
        .setDepth(30);
      const dot = this.add.circle(point.x, point.y, 4, 0x3dbe8b).setDepth(30);
      const crown =
        code === "SUPERVISOR-01"
          ? this.add.graphics().setDepth(31)
          : null;
      if (crown) {
        crown.fillStyle(0xe2c15a, 1);
        crown.fillRect(-7, 0, 14, 3);
        crown.fillRect(-7, -4, 2, 4);
        crown.fillRect(-1, -6, 2, 6);
        crown.fillRect(5, -4, 2, 4);
      }
      const npc: Npc = {
        code,
        sprite,
        label,
        dot,
        crown,
        home,
        tile: home,
        path: [],
        pose: "idle",
        gathered: false,
      };
      this.npcs.set(code, npc);
      this.placeLabel(npc);
    }
    const start = tileCenter(VISITOR_START);
    this.player = this.add
      .sprite(start.x, start.y, "visitor-0")
      .setOrigin(0.5, 0.9)
      .setScale(2)
      .setDepth(start.y)
      .setVisible(false);
    const boardX = BOARDROOM.x * TILE + TILE / 2;
    const boardY = (BOARDROOM.y - 2) * TILE;
    this.add
      .text(boardX, boardY, "BOARDROOM", {
        fontFamily: "IBM Plex Sans, sans-serif",
        fontSize: "16px",
        color: "#e7fff4",
        fontStyle: "700",
      })
      .setOrigin(0.5, 1)
      .setDepth(8);
    this.add
      .text(boardX, boardY + 4, "Wednesday", {
        fontFamily: "IBM Plex Sans, sans-serif",
        fontSize: "13px",
        color: "#8ee0b8",
      })
      .setOrigin(0.5, 0)
      .setDepth(8);
    const signX = SIGN.x * TILE + TILE / 2;
    const signTop = SIGN.y * TILE - 18;
    this.add
      .text(signX, signTop + 28, "VEYTRIX", {
        fontFamily: "IBM Plex Sans, sans-serif",
        fontSize: "13px",
        color: "#e7fff4",
        fontStyle: "700",
      })
      .setOrigin(0.5)
      .setDepth(8);
    this.add
      .text(signX, signTop + 42, "SANCTUM", {
        fontFamily: "IBM Plex Sans, sans-serif",
        fontSize: "10px",
        color: "#3dbe8b",
      })
      .setOrigin(0.5)
      .setDepth(8);
  }

  private makeLabels() {
    for (const npc of this.npcs.values()) {
      this.placeLabel(npc);
    }
  }

  private bindInput() {
    const keyboard = this.input.keyboard;
    if (keyboard) {
      const cursors = keyboard.createCursorKeys();
      const wasd = keyboard.addKeys("W,A,S,D") as {
        W: Phaser.Input.Keyboard.Key;
        A: Phaser.Input.Keyboard.Key;
        S: Phaser.Input.Keyboard.Key;
        D: Phaser.Input.Keyboard.Key;
      };
      this.keys = {
        up: cursors.up,
        down: cursors.down,
        left: cursors.left,
        right: cursors.right,
        w: wasd.W,
        a: wasd.A,
        s: wasd.S,
        d: wasd.D,
      };
    }
    this.input.on("pointerdown", (pointer: Phaser.Input.Pointer) => {
      this.dragging = true;
      this.lastX = pointer.x;
      this.lastY = pointer.y;
      const picked = this.nearestDesk(pointer.worldX, pointer.worldY);
      if (picked) {
        this.bridge.hooks.onSelect(picked);
        if (this.mode === "floor") {
          this.follow(picked);
        }
      }
    });
    this.input.on("pointermove", (pointer: Phaser.Input.Pointer) => {
      if (!this.dragging || !pointer.isDown) {
        return;
      }
      const dx = pointer.x - this.lastX;
      const dy = pointer.y - this.lastY;
      if (Math.hypot(dx, dy) > 4) {
        this.cameras.main.stopFollow();
        this.mode = "pan";
        this.cameras.main.scrollX -= dx / this.cameras.main.zoom;
        this.cameras.main.scrollY -= dy / this.cameras.main.zoom;
      }
      this.lastX = pointer.x;
      this.lastY = pointer.y;
    });
    this.input.on("pointerup", () => {
      this.dragging = false;
    });
    this.input.on(
      "wheel",
      (_pointer: Phaser.Input.Pointer, _objects: unknown, _deltaX: number, deltaY: number) => {
        this.zoomBy(deltaY > 0 ? 0.9 : 1.1);
      },
    );
  }

  private nearestDesk(worldX: number, worldY: number): AgentCode | null {
    let best: AgentCode | null = null;
    let bestDistance = 72;
    for (const npc of this.npcs.values()) {
      const distance = Math.hypot(npc.sprite.x - worldX, npc.sprite.y - worldY);
      if (distance < bestDistance) {
        best = npc.code;
        bestDistance = distance;
      }
    }
    return best;
  }

  private visual(npc: Npc): SpritePose {
    if (npc.path.length > 0) {
      return "walk";
    }
    if (npc.gathered) {
      return "talk";
    }
    if (npc.pose === "working") {
      return "work";
    }
    return "sit";
  }

  private placeLabel(npc: Npc) {
    npc.label.setPosition(npc.sprite.x, npc.sprite.y - 92);
    npc.dot.setPosition(npc.label.x - npc.label.width / 2 - 9, npc.label.y - 10);
    npc.crown?.setPosition(npc.label.x, npc.label.y - 18);
    npc.sprite.setDepth(npc.sprite.y);
  }

  private walk(npc: Npc, goal: Tile, gathered: boolean) {
    const path = findPath(npc.tile, goal, isWalkable);
    npc.path = path.slice(1);
    npc.gathered = gathered;
  }

  private moveNpcs(delta: number) {
    const step = 78 * (delta / 1000);
    for (const npc of this.npcs.values()) {
      const next = npc.path[0];
      if (!next) {
        continue;
      }
      const target = tileCenter(next);
      const dx = target.x - npc.sprite.x;
      const dy = target.y - npc.sprite.y;
      const distance = Math.hypot(dx, dy);
      if (distance <= step || distance === 0) {
        npc.sprite.setPosition(target.x, target.y);
        npc.tile = next;
        npc.path.shift();
      } else {
        npc.sprite.x += (dx / distance) * step;
        npc.sprite.y += (dy / distance) * step;
      }
      this.placeLabel(npc);
    }
  }

  private typing(): boolean {
    const tag = document.activeElement?.tagName;
    return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
  }

  private movePlayer(delta: number) {
    if (this.mode !== "floor" || !this.player.visible || !this.keys || this.typing()) {
      return;
    }
    const keys = this.keys;
    const dirX = (keys.right.isDown || keys.d.isDown ? 1 : 0) - (keys.left.isDown || keys.a.isDown ? 1 : 0);
    const dirY = (keys.down.isDown || keys.s.isDown ? 1 : 0) - (keys.up.isDown || keys.w.isDown ? 1 : 0);
    if (dirX === 0 && dirY === 0) {
      return;
    }
    this.followCode = null;
    this.cameras.main.startFollow(this.player, true, 0.12, 0.12);
    const step = 110 * (delta / 1000);
    const nextX = this.player.x + dirX * step;
    const nextY = this.player.y + dirY * step;
    if (isWalkable(Math.floor(nextX / TILE), Math.floor(this.player.y / TILE))) {
      this.player.x = nextX;
    }
    if (isWalkable(Math.floor(this.player.x / TILE), Math.floor(nextY / TILE))) {
      this.player.y = nextY;
    }
    this.player.setDepth(this.player.y);
  }
}

export function createSanctumGame(parent: HTMLElement, hooks: Hooks): SanctumController {
  const bridge: Bridge = { scene: null, hooks, poses: {}, pendingMode: "sky" };
  const game = new Phaser.Game({
    type: Phaser.AUTO,
    parent,
    backgroundColor: "#070c0a",
    pixelArt: true,
    roundPixels: true,
    banner: false,
    audio: { noAudio: true },
    scale: {
      mode: Phaser.Scale.RESIZE,
      width: Math.max(parent.clientWidth, 320),
      height: Math.max(parent.clientHeight, 320),
    },
    input: { keyboard: true, mouse: true },
    scene: [],
  });
  game.scene.add("hq", HqScene, true, { bridge });
  return {
    destroy() {
      game.destroy(true);
      bridge.scene = null;
    },
    setMode(mode) {
      if (bridge.scene) {
        bridge.scene.applyMode(mode);
      } else {
        bridge.pendingMode = mode;
      }
    },
    panBy(dx, dy) {
      bridge.scene?.panBy(dx, dy);
    },
    zoomBy(factor) {
      bridge.scene?.zoomBy(factor);
    },
    fit() {
      if (bridge.scene) {
        bridge.scene.applyMode("sky");
      } else {
        bridge.pendingMode = "sky";
      }
    },
    follow(code) {
      bridge.scene?.follow(code);
    },
    setPoses(poses) {
      bridge.poses = poses;
      bridge.scene?.applyPoses();
    },
    gather() {
      bridge.scene?.gather();
    },
    returnToDesks() {
      bridge.scene?.returnToDesks();
    },
  };
}
