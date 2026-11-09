import { useEffect, useState } from "react";
import { Link, NavLink } from "react-router-dom";
import { apiGet } from "../api/client";
import {
  type AgentCode,
  type AgentDesk,
  type AgentListResponse,
  type AuditLogListResponse,
  type SystemStatusResponse,
} from "../api/types";
import { isRegistry } from "../sanctum/activity";
import { type ActivityLine } from "../sanctum/ui/ActivityFeed";
import { ChatPanel } from "../sanctum/ui/ChatPanel";
import { ConversationMonitor } from "../sanctum/ui/ConversationMonitor";
import { truncate } from "../comms/speech";
import { useComms } from "../comms/useComms";
import { ORIGIN_TAG } from "../comms/types";
import { Icon } from "../sanctum/ui/Icon";
import { LogPanel, type SanctumLog } from "../sanctum/ui/LogPanel";
import { SkyFloor } from "../sanctum/ui/SkyFloor";
import "../sanctum/ui/sanctum.css";

const NAV = [
  { to: "/sanctum", label: "Sanctum", icon: "home" },
  { to: "/market", label: "Market", icon: "chart" },
  { to: "/portfolio", label: "Portfolio", icon: "case" },
  { to: "/agency", label: "Agents", icon: "users" },
  { to: "/strategy", label: "Strategy", icon: "shield" },
  { to: "/research", label: "Research", icon: "book" },
  { to: "/treasury", label: "Treasury", icon: "vault" },
  { to: "/worldview", label: "Worldview", icon: "globe" },
] as const;

const RAIL = [
  { id: "sky", label: "Sky View", icon: "home" },
  { id: "floor", label: "Floor View", icon: "grid" },
  { id: "agents", label: "Agent List", icon: "users" },
  { id: "activity", label: "Activity", icon: "pulse" },
  { id: "boardroom", label: "Boardroom", icon: "podium" },
  { id: "cameras", label: "Cameras", icon: "camera" },
  { id: "talk", label: "Conversations", icon: "book" },
  { id: "logs", label: "Logs", icon: "list" },
] as const;

type RailId = (typeof RAIL)[number]["id"];

const ROSTER: Record<string, { name: string; role: string }> = {
  "SUPERVISOR-01": { name: "Roads", role: "AI Commander" },
  "DAY-01": { name: "Dayvid", role: "Day desk" },
  "STOCK-01": { name: "Vex", role: "Stock desk" },
  "CRYPTO-01": { name: "Nyx", role: "Crypto desk" },
  "DEFI-01": { name: "Cipher", role: "DeFi desk" },
  "ETF-01": { name: "Lyra", role: "ETF desk" },
  "RESEARCH-01": { name: "Astra", role: "Research desk" },
  "RISK-01": { name: "Aegis", role: "Risk desk" },
  "TREASURY-01": { name: "Midas", role: "Treasury desk" },
  "FUTURES-01": { name: "Futures", role: "Futures desk" },
};

const PERSONAS: Record<string, string> = Object.fromEntries(
  Object.entries(ROSTER).filter(([code]) => code !== "FUTURES-01").map(([code, row]) => [code, row.name]),
);

function deskIdentity(code: string): { name: string; role: string } {
  return ROSTER[code] ?? { name: code, role: "Desk" };
}

function ago(iso: string, now: number): string {
  const seconds = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
  if (Number.isNaN(seconds)) {
    return "";
  }
  if (seconds < 90) {
    return `${seconds}s`;
  }
  const minutes = Math.round(seconds / 60);
  return minutes < 90 ? `${minutes}m` : `${Math.round(minutes / 60)}h`;
}

const ZONES = [
  { label: "Trading desks (4)", color: "#3dff9a" },
  { label: "Research / analysis (2)", color: "#c084fc" },
  { label: "Risk / treasury (2)", color: "#f5c542" },
  { label: "Command center (1)", color: "#22d3ee" },
  { label: "Boardroom (1)", color: "#34d399" },
  { label: "Lounge & workspaces (shared)", color: "#c4a574" },
];

type Shot = { scale: number; x: number; y: number };

const SHOTS: Record<string, Shot> = {
  sky: { scale: 1, x: 0, y: 0 },
  floor: { scale: 1.2, x: 0, y: 10 },
  center: { scale: 1.55, x: 0, y: -10 },
  meeting: { scale: 1.65, x: 0, y: -90 },
  trading: { scale: 1.4, x: 0, y: 20 },
};

type CameraName = keyof typeof SHOTS | "custom";

function formatClock(date: Date): string {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
    timeZoneName: "short",
  }).formatToParts(date);
  const get = (type: Intl.DateTimeFormatPartTypes) => parts.find((part) => part.type === type)?.value ?? "";
  return `${get("weekday")}, ${get("month")} ${get("day")}, ${get("year")} ${get("hour")}:${get("minute")} ${get("dayPeriod")} ${get("timeZoneName")}`;
}

function FeedList({ lines }: { lines: ActivityLine[] }) {
  return (
    <ul className="sx-feed">
      {lines.map((line) => (
        <li key={line.id}>
          <i className="led" />
          <span>{line.message}</span>
          <time>{line.time}</time>
        </li>
      ))}
    </ul>
  );
}

const SIDEBAR_KEY = "veytrix.sanctum.sidebar";

function readSidebarCollapsed(): boolean {
  try {
    return window.localStorage.getItem(SIDEBAR_KEY) === "collapsed";
  } catch {
    return false;
  }
}

export function SanctumPage() {
  const [rail, setRail] = useState<RailId>("sky");
  const [navCollapsed, setNavCollapsed] = useState(readSidebarCollapsed);
  const [shot, setShot] = useState<Shot>(SHOTS.sky);
  const [camera, setCamera] = useState<CameraName>("sky");
  const [selected, setSelected] = useState<AgentCode>("SUPERVISOR-01");
  const [deskOpen, setDeskOpen] = useState(false);
  const [registryDown, setRegistryDown] = useState(false);
  const [agents, setAgents] = useState<AgentDesk[] | null>(null);
  const [personas, setPersonas] = useState(PERSONAS);
  const [logs, setLogs] = useState<SanctumLog[]>([]);
  const [health, setHealth] = useState<string>("unread");
  const [clock, setClock] = useState("");
  const [following, setFollowing] = useState(false);
  const [monitorFollow, setMonitorFollow] = useState<string | null>(null);
  const comms = useComms();

  useEffect(() => {
    try {
      window.localStorage.setItem(SIDEBAR_KEY, navCollapsed ? "collapsed" : "expanded");
    } catch {
      // Storage can be blocked. The choice still applies for this visit.
    }
  }, [navCollapsed]);

  useEffect(() => {
    document.title = "Sanctum · Veytrix";
    const tick = () => setClock(formatClock(new Date()));
    tick();
    const clockId = window.setInterval(tick, 30_000);
    let cancelled = false;
    void apiGet<AgentListResponse>("/api/v1/agents")
      .then((body) => {
        if (cancelled) {
          return;
        }
        if (!isRegistry(body)) {
          setRegistryDown(true);
          return;
        }
        setAgents(body.agents);
      })
      .catch(() => {
        if (!cancelled) {
          setRegistryDown(true);
        }
      });
    void apiGet<{ personas?: Record<string, string> }>("/api/v1/inference/posture")
      .then((body) => {
        if (!cancelled && body.personas) {
          setPersonas((current) => ({ ...current, ...body.personas }));
        }
      })
      .catch(() => undefined);
    void apiGet<SystemStatusResponse>("/api/v1/system/status")
      .then((body) => {
        if (!cancelled) {
          setHealth(body.database === "up" ? "Database up" : "Database down");
        }
      })
      .catch(() => {
        if (!cancelled) {
          setHealth("unread");
        }
      });
    void apiGet<AuditLogListResponse>("/api/v1/audit/log")
      .then((body) => {
        if (cancelled) {
          return;
        }
        setLogs(
          body.events.map((event) => ({
            id: event.id,
            time: event.created_at,
            level: "info" as const,
            service: event.symbol,
            message: `${event.action} ${event.shares} shares. No order is sent.`,
          })),
        );
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
      window.clearInterval(clockId);
    };
  }, []);

  const applyCamera = (name: keyof typeof SHOTS, nextRail?: RailId) => {
    setShot(SHOTS[name]);
    setCamera(name);
    if (nextRail) {
      setRail(nextRail);
      setDeskOpen(false);
    }
  };

  const nudge = (dx: number, dy: number) => {
    setCamera("custom");
    setShot((current) => ({
      ...current,
      x: Math.max(-180, Math.min(180, current.x + dx)),
      y: Math.max(-180, Math.min(180, current.y + dy)),
    }));
  };

  const zoom = (delta: number) => {
    setCamera("custom");
    setShot((current) => ({ ...current, scale: Math.max(0.85, Math.min(1.8, current.scale + delta)) }));
  };

  const selectedAgent = agents?.find((agent) => agent.code === selected);
  const registered = agents?.length ?? 0;
  const rosterRows = (Object.keys(ROSTER) as AgentCode[]).map((code) => {
    const agent = agents?.find((item) => item.code === code);
    const who = deskIdentity(code);
    return {
      code,
      name: who.name,
      role: who.role,
      status: agent?.status ?? "unread",
      display: agent?.display_name ?? "Registry row",
    };
  });
  const auditLines: ActivityLine[] = logs.map((log) => ({
    id: log.id,
    message: log.message,
    time: log.time,
  }));
  const clock0 = Date.now();
  const feedLines: ActivityLine[] =
    comms.feed.length === 0
      ? [
          {
            id: "empty",
            message: "No agent messages are stored yet. Open a desk and ask a question.",
            time: "",
          },
        ]
      : [...comms.feed]
          .reverse()
          .slice(0, 5)
          .map((message) => ({
            id: message.message_id,
            message: `${message.sender_name} · ${message.sender_id}: ${truncate(message.content, 84)} [${ORIGIN_TAG[message.origin]}]`,
            time: ago(message.timestamp, clock0),
          }));
  const showFloor =
    rail === "sky" || rail === "floor" || rail === "cameras" || rail === "boardroom" || rail === "talk";
  const healthy = health === "Database up";
  const agencyLabel = registryDown ? "Registry unavailable" : agents ? "Operational" : "Checking";

  // A plain function, not a component: a component declared here would remount the chat on every render.
  function deskDetail(floating: boolean) {
    const who = deskIdentity(selected);
    return (
      <ChatPanel
        key={selected}
        code={selected}
        name={who.name}
        role={who.role}
        status={`${selectedAgent?.display_name ?? "Registry row"}. Status ${selectedAgent?.status ?? "unread"}`}
        floating={floating}
        following={following}
        onFollow={setFollowing}
        onResult={comms.ingest}
        onClose={() => setDeskOpen(false)}
      />
    );
  }

  return (
    <div className={navCollapsed ? "sanctum is-nav-collapsed" : "sanctum"}>
      <a className="skip-link" href="#sanctum-floor">
        Skip to floor
      </a>
      <header className="sx-top">
        <div className="sx-brand-capsule">
          <Link to="/" className="sx-brand">
            <span className="sx-mark" aria-hidden="true">
              V
            </span>
            VEYTRIX
          </Link>
          <button
            type="button"
            className="sx-collapse"
            aria-expanded={!navCollapsed}
            aria-controls="sanctum-views"
            aria-label={navCollapsed ? "Expand sidebar" : "Minimise sidebar"}
            onClick={() => setNavCollapsed((value) => !value)}
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.7"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d={navCollapsed ? "m9 6 6 6-6 6" : "m15 6-6 6 6 6"} />
            </svg>
          </button>
        </div>
        <nav aria-label="Sanctum" className="sx-nav">
          {NAV.map((item) => (
            <NavLink key={item.to} to={item.to}>
              <Icon name={item.icon} />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="sx-meta">
          <span className="sx-pill">
            <i className="led" />
            Paper
          </span>
          <span className="sx-view-label">
            <Icon name="camera" />
            Sky View
          </span>
          <span className="sx-clock">{clock}</span>
        </div>
      </header>

      <div className={navCollapsed ? "sx-body is-nav-collapsed" : "sx-body"}>
        <nav id="sanctum-views" aria-label="Sanctum views" className="sx-rail" hidden={navCollapsed}>
          <div className="sx-kicker">
            <Icon name="home" />
            Sanctum
          </div>
          {RAIL.map((item) => (
            <button
              key={item.id}
              type="button"
              aria-pressed={rail === item.id}
              onClick={() => {
                setDeskOpen(false);
                if (item.id === "sky") {
                  applyCamera("sky", "sky");
                } else if (item.id === "floor") {
                  applyCamera("floor", "floor");
                } else if (item.id === "boardroom") {
                  applyCamera("meeting", "boardroom");
                } else if (item.id === "cameras") {
                  applyCamera("center", "cameras");
                } else {
                  setRail(item.id);
                }
              }}
            >
              <Icon name={item.icon} />
              {item.label}
            </button>
          ))}
        </nav>

        <main className="sx-main">
          {showFloor ? (
            <SkyFloor
              shot={shot}
              persona={(code) => personas[code] ?? "Desk"}
              selected={deskOpen ? selected : null}
              onDesk={(code) => {
                setSelected(code);
                setDeskOpen(true);
              }}
              onBoardroom={() => applyCamera("meeting", "boardroom")}
              speech={comms.frame.speech}
              gather={comms.frame.gather}
              follow={(following && deskOpen ? selected : (monitorFollow as AgentCode | null)) || null}
              onAvatar={(code) => {
                comms.speakLast(code);
              }}
            />
          ) : null}
          {showFloor && comms.notice ? <p className="cx-floor-note">{comms.notice}</p> : null}
          {showFloor && rail === "floor" ? (
            <p className="floor-caption">Floor view. The desks stay clickable. No order is sent.</p>
          ) : null}
          {showFloor && rail === "cameras" ? (
            <p className="floor-caption">Cameras frame the floor. Pan and zoom stay on the floor. No order is sent.</p>
          ) : null}
          {showFloor && rail === "boardroom" ? (
            <aside className="floor-note">
              <h2>Wednesday boardroom</h2>
              <p>12 Nov 2026, 9:00 AM EST</p>
              <p>
                Convene a session from Conversations. No calendar event is created. No order is sent.
              </p>
              <ul>
                {rosterRows.map((row) => (
                  <li key={row.code}>
                    {row.name} · {row.code} · {row.role}
                  </li>
                ))}
              </ul>
            </aside>
          ) : null}
          {showFloor && deskOpen ? deskDetail(true) : null}

          {rail === "agents" ? (
            <div id="sanctum-floor" className="alt-view alt-grid">
              <div>
                <h2>Agent list</h2>
                <p className="sx-note">Ten desks. None can trade. No order is sent.</p>
                <ul className="roster">
                  {rosterRows.map((row) => (
                    <li key={row.code}>
                      <button
                        type="button"
                        className="roster-btn"
                        aria-pressed={selected === row.code}
                        onClick={() => {
                          setSelected(row.code);
                          setDeskOpen(true);
                        }}
                      >
                        <strong>{row.name}</strong>
                        <span>{row.code}</span>
                        <span>{row.role}</span>
                        <span>Status {row.status}</span>
                      </button>
                    </li>
                  ))}
                </ul>
                <p className="sx-note">Orders, signing, and transfers stay refused.</p>
              </div>
              {deskDetail(false)}
            </div>
          ) : null}

          {rail === "activity" ? (
            <div id="sanctum-floor" className="alt-view">
              <h2>Live activity feed</h2>
              <FeedList lines={feedLines} />
              <h2 className="view-gap">Local audit</h2>
              {auditLines.length === 0 ? (
                <p className="sx-note">No audit rows yet. No order is sent.</p>
              ) : (
                <FeedList lines={auditLines} />
              )}
            </div>
          ) : null}

          {rail === "talk" ? (
            <aside className="cx-drawer" aria-label="Conversations">
              <ConversationMonitor comms={comms} onFollowAgent={setMonitorFollow} />
            </aside>
          ) : null}

          {rail === "logs" ? (
            <div id="sanctum-floor" className="alt-view">
              <h2>Audit log</h2>
              <p className="sx-note">Local size rows only. No payment log is invented. No order is sent.</p>
              {logs.length === 0 ? (
                <p className="sx-note">No audit rows yet.</p>
              ) : (
                <LogPanel logs={logs} />
              )}
            </div>
          ) : null}
        </main>

        <aside className="sx-side">
          <div className="sx-title">
            <Icon name="bars" />
            <div>
              <h1>Sanctum — Sky View</h1>
              <p>Live Agency Operations</p>
            </div>
          </div>
          <section className="sx-block">
            <h2>Agency Status</h2>
            <p className={registryDown ? "sx-op warn" : "sx-op"}>
              <i className={`led ${registryDown ? "tone-red" : ""}`} />
              {agencyLabel}
            </p>
            <dl className="sx-stats">
              <div>
                <i className="led" />
                <dt>Agents Online</dt>
                <dd>
                  {registered} / 10
                </dd>
              </div>
              <div>
                <i className="led tone-amber" />
                <dt>Active Tasks</dt>
                <dd>0</dd>
              </div>
              <div>
                <i className="led tone-amber" />
                <dt>Trades (Paper)</dt>
                <dd>0</dd>
              </div>
              <div>
                <i className={`led ${registryDown ? "tone-red" : ""}`} />
                <dt>Alerts</dt>
                <dd>{registryDown ? "1" : "0"}</dd>
              </div>
            </dl>
            <p className="sx-note" style={{ marginTop: 6 }}>
              No order is sent.
            </p>
          </section>
          <section className="sx-block">
            <h2>Live Activity Feed</h2>
            <FeedList lines={feedLines} />
            <p className="sx-note" style={{ marginTop: 6 }}>
              {comms.available
                ? comms.realtime === "not_configured"
                  ? "Stored messages only. Realtime is not configured."
                  : comms.realtime === "connected"
                    ? "Stored messages only. Realtime doorbell connected."
                    : "Stored messages only. Realtime is not connected; polling."
                : "Conversation API unavailable. Restart the API from this branch."}
            </p>
          </section>
          <section className="sx-block">
            <h2>Camera Controls</h2>
            <div className="sx-cam">
              <button type="button" aria-label="Pan left" onClick={() => nudge(36, 0)}>
                ‹
              </button>
              <button type="button" aria-label="Pan right" onClick={() => nudge(-36, 0)}>
                ›
              </button>
              <button type="button" aria-label="Pan up" onClick={() => nudge(0, 36)}>
                ⌃
              </button>
              <button type="button" aria-label="Pan down" onClick={() => nudge(0, -36)}>
                ⌄
              </button>
              <button type="button" aria-label="Zoom out" onClick={() => zoom(-0.15)}>
                −
              </button>
              <button type="button" aria-label="Zoom in" onClick={() => zoom(0.15)}>
                +
              </button>
              <button type="button" aria-label="Fit the floor" onClick={() => applyCamera("sky", "sky")}>
                ◎
              </button>
            </div>
            <div className="sx-presets">
              <button type="button" aria-pressed={camera === "sky"} onClick={() => applyCamera("sky", "sky")}>
                Full Floor
              </button>
              <button type="button" aria-pressed={camera === "center"} onClick={() => applyCamera("center", "cameras")}>
                Center
              </button>
              <button type="button" aria-pressed={camera === "meeting"} onClick={() => applyCamera("meeting", "boardroom")}>
                Meeting
              </button>
              <button
                type="button"
                aria-pressed={camera === "trading"}
                title="Frame the trading desks. No order is sent."
                onClick={() => applyCamera("trading", "floor")}
              >
                Trading
              </button>
            </div>
          </section>
          <section className="sx-block">
            <h2>Floor Zones (One Floor)</h2>
            <ul className="sx-zones">
              {ZONES.map((zone) => (
                <li key={zone.label} className="sx-zone">
                  <i className="swatch" style={{ background: zone.color }} />
                  {zone.label}
                </li>
              ))}
            </ul>
          </section>
        </aside>
      </div>

      <footer className="sx-foot">
        <div className="sx-who">
          <span className="sx-avatar" aria-hidden="true" />
          <div>
            <strong>Roads</strong>
            <p className="sx-k">SUPERVISOR-01 · AI Commander</p>
            <p className="sx-live">
              <i className="led" />
              Active
            </p>
          </div>
        </div>
        <div className="sx-focus">
          <Icon name="target" />
          <div>
            <p className="sx-k">Current Focus</p>
            <strong>Agency Coordination</strong>
          </div>
        </div>
        <div className="sx-event">
          <Icon name="calendar" />
          <div>
            <p className="sx-k">Next Event</p>
            <strong>Wednesday Boardroom</strong>
            <p className="sx-k">Nov 12, 2026 • 9:00 AM EST</p>
          </div>
        </div>
        <div className="sx-health">
          <Icon name="bars" />
          <div>
            <p className="sx-k">System Health</p>
            <div className="sx-bars" aria-hidden="true">
              {Array.from({ length: 12 }, (_, index) => (
                <i key={index} className={healthy ? "on" : ""} />
              ))}
            </div>
            <strong>{healthy ? "100%" : health === "Database down" ? "Down" : "unread"}</strong>
          </div>
        </div>
        <div className="sx-count">
          <Icon name="users" />
          <div>
            <p className="sx-k">AI Agents</p>
            <strong>
              {registered} / 10 Online
            </strong>
          </div>
        </div>
        <div>
          <p className="sx-k">Trading Mode</p>
          <p className="sx-mode">
            <Icon name="monitor" />
            Simulation (Paper)
          </p>
        </div>
        <Link to="/settings" className="sx-gear" aria-label="Settings">
          <Icon name="gear" />
        </Link>
      </footer>

      {registryDown ? (
        <p className="vx-alert sx-alert" role="alert">
          Agent registry is unavailable. No desk was invented. No order was sent.
        </p>
      ) : null}
    </div>
  );
}
