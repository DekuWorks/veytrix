import { useEffect, useRef, useState } from "react";
import type { AgentCode } from "../../api/types";
import "./sanctum.css";

const SPINES = ["#7f1d1d", "#1d4ed8", "#166534", "#a16207", "#6b21a8", "#0f766e", "#9a3412", "#1e3a8a", "#365314", "#b45309", "#831843", "#134e4a"];

type Face = "north" | "south" | "east" | "west";

const DESKS: {
  code: AgentCode;
  top: string;
  left: string;
  face: Face;
  screens: number;
  hair: string;
  shirt: string;
  screen: string;
}[] = [
  { code: "RESEARCH-01", top: "28%", left: "24%", face: "south", screens: 3, hair: "#60a5fa", shirt: "#1e3a8a", screen: "#67e8f9" },
  { code: "ETF-01", top: "24%", left: "40%", face: "south", screens: 2, hair: "#e7e5e4", shirt: "#334155", screen: "#7dd3fc" },
  { code: "DEFI-01", top: "24%", left: "60%", face: "south", screens: 3, hair: "#c084fc", shirt: "#581c87", screen: "#d8b4fe" },
  { code: "CRYPTO-01", top: "28%", left: "76%", face: "south", screens: 2, hair: "#111827", shirt: "#14532d", screen: "#4ade80" },
  { code: "STOCK-01", top: "44%", left: "22%", face: "east", screens: 3, hair: "#f87171", shirt: "#7f1d1d", screen: "#22d3ee" },
  { code: "FUTURES-01", top: "44%", left: "74%", face: "west", screens: 2, hair: "#0f172a", shirt: "#064e3b", screen: "#2dd4bf" },
  { code: "RISK-01", top: "54%", left: "80%", face: "west", screens: 3, hair: "#d6d3d1", shirt: "#292524", screen: "#fbbf24" },
  { code: "DAY-01", top: "60%", left: "32%", face: "north", screens: 2, hair: "#4ade80", shirt: "#14532d", screen: "#86efac" },
  { code: "TREASURY-01", top: "58%", left: "66%", face: "north", screens: 2, hair: "#312e81", shirt: "#1e3a8a", screen: "#93c5fd" },
];

const LAMPS = [
  { top: "20%", left: "16%" },
  { top: "20%", left: "84%" },
  { top: "40%", left: "16%" },
  { top: "40%", left: "84%" },
  { top: "62%", left: "18%" },
  { top: "62%", left: "78%" },
  { top: "86%", left: "40%" },
  { top: "86%", left: "60%" },
];

const PLANTS = [
  { top: "16%", left: "14%" },
  { top: "16%", left: "86%" },
  { top: "46%", left: "14%" },
  { top: "46%", left: "86%" },
  { top: "74%", left: "6%" },
  { top: "88%", left: "5%" },
  { top: "58%", left: "93%" },
  { top: "76%", left: "93%" },
  { top: "90%", left: "90%" },
  { top: "92%", left: "34%" },
];

type Spot = { x: number; y: number };

const CENTRE: Spot = { x: 50, y: 46 };
const MEETING: Spot = { x: 50, y: 74 };

const CREW: {
  code: AgentCode;
  name: string;
  role: string;
  home: Spot;
  hair: string;
  shirt: string;
}[] = [
  { code: "SUPERVISOR-01", name: "Roads", role: "AI Commander", home: { x: 50, y: 58 }, hair: "#3b82f6", shirt: "#14532d" },
  { code: "RESEARCH-01", name: "Astra", role: "Research desk", home: { x: 28, y: 34 }, hair: "#60a5fa", shirt: "#1e3a8a" },
  { code: "ETF-01", name: "Lyra", role: "ETF desk", home: { x: 40, y: 30 }, hair: "#e7e5e4", shirt: "#334155" },
  { code: "DEFI-01", name: "Cipher", role: "DeFi desk", home: { x: 60, y: 30 }, hair: "#c084fc", shirt: "#581c87" },
  { code: "CRYPTO-01", name: "Nyx", role: "Crypto desk", home: { x: 76, y: 34 }, hair: "#111827", shirt: "#14532d" },
  { code: "STOCK-01", name: "Vex", role: "Stock desk", home: { x: 28, y: 48 }, hair: "#f87171", shirt: "#7f1d1d" },
  { code: "FUTURES-01", name: "Futures", role: "Futures desk", home: { x: 70, y: 48 }, hair: "#0f172a", shirt: "#064e3b" },
  { code: "RISK-01", name: "Aegis", role: "Risk desk", home: { x: 76, y: 58 }, hair: "#d6d3d1", shirt: "#292524" },
  { code: "DAY-01", name: "Dayvid", role: "Day desk", home: { x: 36, y: 64 }, hair: "#4ade80", shirt: "#14532d" },
  { code: "TREASURY-01", name: "Midas", role: "Treasury desk", home: { x: 64, y: 62 }, hair: "#312e81", shirt: "#1e3a8a" },
];

const ROUTE_STOPS = [CENTRE, MEETING] as const;

type Shot = { scale: number; x: number; y: number };

type SkyFloorProps = {
  shot: Shot;
  persona: (code: string) => string;
  selected: AgentCode | null;
  onDesk: (code: AgentCode) => void;
  onBoardroom: () => void;
  onTalk: (code: AgentCode) => Promise<string>;
};

function clampSpot(spot: Spot): Spot {
  return {
    x: Math.max(16, Math.min(84, spot.x)),
    y: Math.max(20, Math.min(80, spot.y)),
  };
}

function stepToward(from: Spot, to: Spot): Spot {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const distance = Math.hypot(dx, dy);
  if (distance < 0.7) {
    return to;
  }
  const pace = Math.min(1.3, distance);
  return clampSpot({ x: from.x + (dx / distance) * pace, y: from.y + (dy / distance) * pace });
}

function Figure({ hair, shirt }: { hair: string; shirt: string }) {
  return (
    <span className="fig" style={{ ["--hair" as string]: hair, ["--shirt" as string]: shirt }}>
      <span className="hair" />
      <span className="head" />
      <span className="torso" />
    </span>
  );
}

function Shelf({ side }: { side: "l" | "r" }) {
  return (
    <div className={`shelf ${side}`} aria-hidden="true">
      {SPINES.map((color) => (
        <i key={`${side}-${color}`} style={{ ["--c" as string]: color }} />
      ))}
    </div>
  );
}

/** Sky-view floor built from HTML and CSS. No picture. */
export function SkyFloor({ shot, persona, selected, onDesk, onBoardroom, onTalk }: SkyFloorProps) {
  const [spots, setSpots] = useState<Record<string, Spot>>(() =>
    Object.fromEntries(CREW.map((member) => [member.code, member.home])),
  );
  const [bubbles, setBubbles] = useState<Record<string, string>>({});
  const goals = useRef<Record<string, Spot>>(Object.fromEntries(CREW.map((member) => [member.code, member.home])));
  const hop = useRef(0);
  const talking = useRef(false);
  const onTalkRef = useRef(onTalk);
  onTalkRef.current = onTalk;

  async function showLine(code: AgentCode) {
    const member = CREW.find((item) => item.code === code);
    const fallback = member?.name ?? code;
    try {
      const line = await onTalkRef.current(code);
      setBubbles((current) => ({ ...current, [code]: line }));
    } catch {
      setBubbles((current) => ({ ...current, [code]: `${fallback}: Route failed. No order is sent.` }));
    }
    window.setTimeout(() => {
      setBubbles((current) => ({ ...current, [code]: "" }));
    }, 7000);
  }

  useEffect(() => {
    const reduce =
      typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) {
      return undefined;
    }
    const move = window.setInterval(() => {
      setSpots((current) => {
        const next: Record<string, Spot> = {};
        for (const member of CREW) {
          next[member.code] = stepToward(current[member.code] ?? member.home, goals.current[member.code] ?? member.home);
        }
        return next;
      });
    }, 220);
    const wander = window.setInterval(() => {
      const member = CREW[hop.current % CREW.length];
      hop.current += 1;
      const stop = hop.current % 3 === 0 ? member.home : ROUTE_STOPS[hop.current % ROUTE_STOPS.length];
      goals.current[member.code] = stop;
    }, 2800);
    return () => {
      window.clearInterval(move);
      window.clearInterval(wander);
    };
  }, []);

  useEffect(() => {
    if (talking.current) {
      return;
    }
    const pair = CREW.find((member, index) =>
      CREW.slice(index + 1).some((other) => {
        const a = spots[member.code];
        const b = spots[other.code];
        if (!a || !b) {
          return false;
        }
        return Math.hypot(a.x - b.x, a.y - b.y) < 7 && !bubbles[member.code] && !bubbles[other.code];
      }),
    );
    if (!pair) {
      return;
    }
    talking.current = true;
    void showLine(pair.code).finally(() => {
      talking.current = false;
    });
  }, [spots, bubbles]);

  return (
    <div id="sanctum-floor" tabIndex={-1} className="sky-floor">
      <div
        className="sky-cam"
        style={{ transform: `translate(${shot.x}px, ${shot.y}px) scale(${shot.scale})` }}
      >
        <div className="sky-world">
          <div className="plate hall" />
          <div className="plate wing-l" />
          <div className="plate wing-r" />
          <div className="plate room-b" />
          <div className="door" style={{ left: "9%", top: "56%", width: "8%", height: "16%" }} />
          <div className="door" style={{ left: "83%", top: "56%", width: "8%", height: "16%" }} />
          <div className="door" style={{ left: "40%", top: "68%", width: "20%", height: "8%" }} />

          <div className="tree" style={{ left: "7%", top: "1%" }} aria-hidden="true">
            <i />
            <i />
            <i />
            <b />
          </div>
          <div className="tree" style={{ right: "7%", top: "1%" }} aria-hidden="true">
            <i />
            <i />
            <i />
            <b />
          </div>

          <Shelf side="l" />
          <Shelf side="r" />
          <div className="sign" aria-hidden="true">
            <div className="v">V</div>
            <span className="k">VEYTRIX</span>
            <span className="n">SANCTUM</span>
          </div>
          <div className="path-v" />
          <div className="neon-inset" />

          <div className="pool" />
          <div className="sofa a" />
          <div className="sofa b" />
          <div className="rtable" style={{ left: "88%", top: "56%" }} />
          <div className="rtable" style={{ left: "91%", top: "70%" }} />
          <div className="rtable" style={{ left: "87%", top: "82%" }} />

          {LAMPS.map((lamp) => (
            <span key={`${lamp.top}-${lamp.left}`} className="lamp" style={lamp} />
          ))}
          {PLANTS.map((plant) => (
            <span key={`${plant.top}-${plant.left}`} className="plant" style={plant} />
          ))}
          {DESKS.map((desk) => (
            <button
              key={desk.code}
              type="button"
              className="sky-desk"
              style={{ top: desk.top, left: desk.left }}
              title={persona(desk.code)}
              aria-pressed={selected === desk.code}
              onClick={() => onDesk(desk.code)}
            >
              <span className="tag">
                <i className="led" />
                {desk.code}
              </span>
              <span
                className="station"
                data-face={desk.face}
                style={{ ["--screen" as string]: desk.screen }}
                aria-hidden="true"
              >
                <span className="mons">
                  {Array.from({ length: desk.screens }, (_, index) => (
                    <span key={index} className="mon" />
                  ))}
                </span>
              </span>
            </button>
          ))}

          {CREW.map((member) => {
            const spot = spots[member.code] ?? member.home;
            return (
              <div key={member.code} className="bot" style={{ top: `${spot.y}%`, left: `${spot.x}%` }}>
                {bubbles[member.code] ? <p className="thought">{bubbles[member.code]}</p> : null}
                <button
                  type="button"
                  aria-pressed={selected === member.code}
                  onClick={() => {
                    onDesk(member.code);
                    void showLine(member.code);
                  }}
                >
                  <span className="nameplate">
                    <span className="nameplate-name">{member.name}</span>
                    <span className="nameplate-role">{member.role}</span>
                  </span>
                  <Figure hair={member.hair} shirt={member.shirt} />
                </button>
              </div>
            );
          })}

          <button
            type="button"
            className="boss"
            title={persona("SUPERVISOR-01")}
            aria-pressed={selected === "SUPERVISOR-01"}
            onClick={() => onDesk("SUPERVISOR-01")}
          >
            <span className="hex" aria-hidden="true">
              <span className="globe" />
            </span>
            <span className="tag">
              <i className="crown" />
              SUPERVISOR-01
            </span>
          </button>

          <button type="button" className="board" onClick={onBoardroom}>
            <span className="tag">
              <i className="led" />
              BOARDROOM
            </span>
            <span className="board-sub">(Wednesdays)</span>
            <span className="b-room" aria-hidden="true">
              <span className="b-table">V</span>
            </span>
          </button>
        </div>
      </div>
    </div>
  );
}
