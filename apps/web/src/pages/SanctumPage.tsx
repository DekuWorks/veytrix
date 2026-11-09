import { useEffect, useRef, useState } from "react";
import { Link, NavLink } from "react-router-dom";
import { apiGet } from "../api/client";
import {
  AGENT_CODES,
  type AgentCode,
  type AgentDesk,
  type AgentListResponse,
  type DeskDetail,
  type FuturesPostureResponse,
} from "../api/types";
import {
  activityFeed,
  agencyStatus,
  agentStat,
  deskHealth,
  isDeskDetail,
  isFuturesPosture,
  isRegistry,
  paperTradeStat,
  poseFor,
  poseFromBroadcast,
  systemHealth,
  taskHistory,
  verifiedTrading,
  type DeskPose,
} from "../sanctum/activity";
import { FLOOR_ORDER } from "../sanctum/floor";
import type { SanctumController, SanctumMode } from "../sanctum/game";
import { openSanctumChannel } from "../sanctum/realtime";
import { renderAgent } from "../sanctum/sprites";
import { formatClock, formatLongDate, newYorkDate, nextWednesday } from "../sanctum/wednesday";

const NAV = [
  { to: "/sanctum", label: "Sanctum" },
  { to: "/market", label: "Market" },
  { to: "/portfolio", label: "Portfolio" },
  { to: "/agency", label: "Agents" },
  { to: "/strategy", label: "Strategy" },
  { to: "/research", label: "Research" },
  { to: "/treasury", label: "Treasury" },
] as const;

const RAIL = [
  { id: "sky", label: "Sky View" },
  { id: "floor", label: "Floor View" },
  { id: "agents", label: "Agent List" },
  { id: "activity", label: "Activity" },
  { id: "boardroom", label: "Boardroom" },
  { id: "cameras", label: "Cameras" },
  { id: "logs", label: "Logs" },
] as const;

type RailId = (typeof RAIL)[number]["id"];

const ZONES = [
  { colour: "#3dbe8b", label: "Trading Desks (4)" },
  { colour: "#8b6bb8", label: "Research / Analysis (2)" },
  { colour: "#c46a6a", label: "Risk / Treasury (2)" },
  { colour: "#3dbe8b", label: "Command Center (1)" },
  { colour: "#d4b15a", label: "Boardroom (1)" },
  { colour: "#8a8478", label: "Lounge & Workspaces (Shared)" },
] as const;

type AuditRow = { created_at: string; action: string };

type Snapshot = {
  loaded: boolean;
  ready: boolean;
  agents: AgentDesk[] | null;
  futuresNote: string | null;
  futuresBad: boolean;
  futuresAlert: boolean;
  audit: AuditRow[] | null;
  trades: { value: string; detail: string };
  verified: string;
  health: string;
  reminders: { close: string; review: string } | null;
  notes: string | null;
  alerts: number;
};

const EMPTY: Snapshot = {
  loaded: false,
  ready: false,
  agents: null,
  futuresNote: null,
  futuresBad: false,
  futuresAlert: false,
  audit: null,
  trades: { value: "not verified", detail: "Ledger unread" },
  verified: "none verified",
  health: "not verified",
  reminders: null,
  notes: null,
  alerts: 0,
};

function readAudit(value: unknown): AuditRow[] | null {
  if (typeof value !== "object" || value === null) {
    return null;
  }
  const record = value as { events?: unknown; order_submitted?: unknown; source?: unknown };
  if (record.source !== "local_audit_log" || record.order_submitted !== false || !Array.isArray(record.events)) {
    return null;
  }
  const rows: AuditRow[] = [];
  for (const event of record.events) {
    if (typeof event !== "object" || event === null) {
      return null;
    }
    const row = event as { created_at?: unknown; action?: unknown; order_submitted?: unknown };
    if (row.order_submitted !== false || row.action !== "risk.size.recorded" || typeof row.created_at !== "string") {
      return null;
    }
    rows.push({ created_at: row.created_at, action: row.action });
  }
  return rows;
}

function readReminders(value: unknown): { close: string; review: string } | null {
  if (typeof value !== "object" || value === null) {
    return null;
  }
  const row = value as {
    accounting_close_on?: unknown;
    payout_review_on?: unknown;
    meeting_time?: unknown;
    daypilot?: unknown;
    event_created?: unknown;
  };
  if (
    row.meeting_time !== "unconfirmed" ||
    row.daypilot !== "absent" ||
    row.event_created !== false ||
    typeof row.accounting_close_on !== "string" ||
    typeof row.payout_review_on !== "string"
  ) {
    return null;
  }
  return { close: row.accounting_close_on, review: row.payout_review_on };
}

function posesFor(snapshot: Snapshot): Record<AgentCode, DeskPose> {
  const poses = {} as Record<AgentCode, DeskPose>;
  for (const code of AGENT_CODES) {
    const agent = snapshot.agents?.find((item) => item.code === code);
    poses[code] = poseFor(agent, snapshot.ready);
  }
  if (snapshot.futuresBad) {
    poses["FUTURES-01"] = "error";
  }
  return poses;
}

function Portrait({ code }: { code: AgentCode }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current;
    const context = canvas?.getContext("2d");
    if (!canvas || !context) {
      return;
    }
    try {
      const pix = renderAgent(code, "sit", 0);
      const source = document.createElement("canvas");
      source.width = pix.width;
      source.height = pix.height;
      source.getContext("2d")?.putImageData(new ImageData(new Uint8ClampedArray(pix.data), pix.width, pix.height), 0, 0);
      context.imageSmoothingEnabled = false;
      context.clearRect(0, 0, canvas.width, canvas.height);
      context.drawImage(source, 8, 2, 40, 60);
    } catch {
      context.clearRect(0, 0, canvas.width, canvas.height);
    }
  }, [code]);
  return <canvas ref={ref} width={56} height={64} aria-hidden="true" className="h-14 w-14" />;
}

export function SanctumPage() {
  const floorRef = useRef<HTMLDivElement>(null);
  const gameRef = useRef<SanctumController | null>(null);
  const snapshotRef = useRef<Snapshot>(EMPTY);
  const selectRef = useRef<(code: AgentCode) => void>(() => undefined);
  const [rail, setRail] = useState<RailId>("sky");
  const [selected, setSelected] = useState<AgentCode>("SUPERVISOR-01");
  const [detailOpen, setDetailOpen] = useState(false);
  const [snapshot, setSnapshot] = useState<Snapshot>(EMPTY);
  const [clock, setClock] = useState(() => formatClock(new Date()));
  const [wednesday] = useState(() => nextWednesday(new Date()));
  const [feedMode, setFeedMode] = useState<"poll" | "realtime">("poll");
  const [realtimeNote, setRealtimeNote] = useState("Supabase Realtime is not configured. Status is the FastAPI poll.");
  const [draft, setDraft] = useState("");
  const [notes, setNotes] = useState<string[]>([]);

  selectRef.current = (code) => {
    setSelected(code);
    setDetailOpen(true);
  };
  snapshotRef.current = snapshot;

  useEffect(() => {
    document.title = "Sanctum · Veytrix";
  }, []);

  useEffect(() => {
    const parent = floorRef.current;
    if (!parent) {
      return undefined;
    }
    let controller: SanctumController | null = null;
    let cancelled = false;
    void import("../sanctum/game").then(({ createSanctumGame }) => {
      if (cancelled || !floorRef.current) {
        return;
      }
      controller = createSanctumGame(floorRef.current, {
        onSelect: (code) => selectRef.current(code),
      });
      gameRef.current = controller;
      controller.setPoses(posesFor(snapshotRef.current));
    });
    return () => {
      cancelled = true;
      controller?.destroy();
      gameRef.current = null;
    };
  }, []);

  useEffect(() => {
    gameRef.current?.setPoses(posesFor(snapshot));
  }, [snapshot]);

  useEffect(() => {
    let cancelled = false;
    const load = () => {
      const today = newYorkDate(new Date());
      void Promise.all([
        apiGet<AgentListResponse>("/api/v1/agents").then(
          (payload) => payload,
          () => null,
        ),
        apiGet<FuturesPostureResponse>("/api/v1/futures/posture").then(
          (payload) => payload,
          () => null,
        ),
        apiGet<unknown>("/api/v1/audit/log").then(
          (payload) => payload,
          () => null,
        ),
        apiGet<unknown>("/api/v1/ledger/reconciliation").then(
          (payload) => payload,
          () => null,
        ),
        apiGet<{ status?: string }>("/api/v1/health").then(
          (payload) => payload,
          () => null,
        ),
        apiGet<{ live_broker?: string; trading_mode?: string; execution_permitted?: boolean }>("/api/v1/diagnostics").then(
          (payload) => payload,
          () => null,
        ),
        apiGet<unknown>(`/api/v1/treasury/reminders?year=${today.year}&month=${today.month}`).then(
          (payload) => payload,
          () => null,
        ),
        apiGet<DeskDetail>(`/api/v1/agency/desks/${selected}`).then(
          (payload) => payload,
          () => null,
        ),
      ]).then(([agents, futures, audit, recon, health, diagnostics, reminders, detail]) => {
        if (cancelled) {
          return;
        }
        const registry = agents && isRegistry(agents) ? agents : null;
        const postureOk = futures ? isFuturesPosture(futures) : false;
        const auditRows = audit ? readAudit(audit) : null;
        const healthOk = health?.status === "ok";
        const brokerDisabled =
          diagnostics?.live_broker === "disabled" &&
          diagnostics.trading_mode === "paper" &&
          diagnostics.execution_permitted === false;
        let alerts = 0;
        if (!registry) {
          alerts += 1;
        }
        if (!postureOk) {
          alerts += 1;
        }
        if (!auditRows) {
          alerts += 1;
        }
        if (paperTradeStat(recon).detail === "Ledger unread") {
          alerts += 1;
        }
        if (!healthOk) {
          alerts += 1;
        }
        setSnapshot({
          loaded: true,
          ready: registry !== null,
          agents: registry?.agents ?? null,
          futuresNote: postureOk && futures ? futures.note : null,
          futuresBad: futures !== null && !postureOk,
          futuresAlert: !postureOk,
          audit: auditRows,
          trades: paperTradeStat(recon),
          verified: verifiedTrading(recon),
          health: systemHealth(healthOk, brokerDisabled),
          reminders: readReminders(reminders),
          notes: detail && isDeskDetail(detail, selected) ? detail.notes : null,
          alerts,
        });
      });
    };
    load();
    const timer = window.setInterval(load, 15000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [selected]);

  useEffect(() => {
    const timer = window.setInterval(() => setClock(formatClock(new Date())), 30000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    let closed = false;
    let closer: (() => void) | null = null;
    void openSanctumChannel(
      {
        url: import.meta.env.VITE_SUPABASE_URL,
        anonKey: import.meta.env.VITE_SUPABASE_ANON_KEY,
      },
      (payload) => {
        const parsed = poseFromBroadcast(payload);
        setRealtimeNote(
          parsed
            ? `${parsed.code} realtime event is not used as a trade.`
            : "Realtime event ignored. It is not a verified trade.",
        );
      },
    ).then((feed) => {
      if (closed) {
        feed.close();
        return;
      }
      closer = feed.close;
      setFeedMode(feed.mode);
      if (feed.mode === "poll") {
        setRealtimeNote("Supabase Realtime is not configured. Status is the FastAPI poll.");
      }
    });
    return () => {
      closed = true;
      closer?.();
    };
  }, []);

  const setCamera = (mode: SanctumMode, nextRail?: RailId) => {
    gameRef.current?.setMode(mode);
    if (nextRail) {
      setRail(nextRail);
    }
  };

  const selectedAgent = snapshot.agents?.find((agent) => agent.code === selected) ?? null;
  const runningLabel = snapshot.agents
    ? String(snapshot.agents.filter((agent) => agent.status !== "disabled" && agent.status !== "paused").length)
    : "not verified";
  const paperLine = snapshot.trades.value === "0" ? "0 verified paper trades" : snapshot.trades.detail;
  const feed = activityFeed({
    agents: snapshot.agents ? FLOOR_ORDER.map((code) => {
      const agent = snapshot.agents?.find((item) => item.code === code);
      return { code, status: agent?.status ?? "unavailable" };
    }) : null,
    futuresNote: snapshot.futuresNote,
    audit: snapshot.audit,
  });
  const counts = agentStat(snapshot.agents);

  return (
    <div className="flex h-screen flex-col bg-[#070c0a] text-ink">
      <a className="skip-link" href="#sanctum-floor">
        Skip to floor
      </a>
      <header className="flex h-14 shrink-0 items-center gap-4 border-b border-line bg-[#0c1210] px-4">
        <Link to="/" className="flex items-center gap-2" aria-label="Veytrix overview">
          <span className="grid h-8 w-8 place-items-center rounded-md border border-jade text-sm font-semibold text-jade">
            V
          </span>
          <span className="text-sm font-semibold tracking-[0.14em]">VEYTRIX</span>
        </Link>
        <nav aria-label="Sanctum" className="flex items-center gap-1">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `rounded-md px-2.5 py-1.5 text-sm ${isActive ? "text-jade" : "text-muted hover:text-ink"}`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-3 text-xs">
          <span
            className="rounded-full bg-jade px-2 py-0.5 text-[10px] font-semibold tracking-wide text-[#062018]"
            title="Sky-view camera. Live broker is disabled. No order is sent."
          >
            LIVE
            <span className="sr-only"> camera. Live broker is disabled. No order is sent.</span>
          </span>
          <button type="button" className="text-sm text-jade" onClick={() => setCamera("sky", "sky")}>
            Sky View
          </button>
          <time className="text-muted" dateTime={new Date().toISOString()}>
            {clock}
          </time>
        </div>
      </header>
      <div className="grid min-h-0 flex-1 grid-cols-[208px_minmax(0,1fr)_300px]">
        <nav aria-label="Sanctum views" className="flex flex-col gap-1 border-r border-line bg-[#0c1210] p-3">
          <p className="px-2 pb-2 text-sm font-semibold text-jade">Sanctum</p>
          {RAIL.map((item) => (
            <button
              key={item.id}
              type="button"
              aria-pressed={rail === item.id}
              className={`rounded-md border-l-2 px-3 py-2 text-left text-sm ${
                rail === item.id
                  ? "border-jade bg-[#12352a] text-jade"
                  : "border-transparent text-muted hover:bg-panel-2 hover:text-ink"
              }`}
              onClick={() => {
                if (item.id === "sky") {
                  setCamera("sky", "sky");
                } else if (item.id === "floor") {
                  setCamera("floor", "floor");
                } else if (item.id === "boardroom") {
                  setCamera("meeting", "boardroom");
                } else {
                  setRail(item.id);
                }
              }}
            >
              {item.label}
            </button>
          ))}
        </nav>
        <div className="relative min-h-0 min-w-0 bg-[#070c0a]">
          <div ref={floorRef} id="sanctum-floor" tabIndex={-1} className="absolute inset-0 outline-none" />
          <ul className="sr-only" aria-label="Desks on the floor">
            {FLOOR_ORDER.map((code) => (
              <li key={code}>{code}</li>
            ))}
          </ul>
          <p className="sr-only">BOARDROOM</p>
          {detailOpen ? (
            <section
              role="dialog"
              aria-label={`${selected} detail`}
              className="absolute bottom-3 left-3 right-3 z-10 max-h-[46%] overflow-auto rounded-md border border-line bg-[#0c1210]/95 p-4 text-sm"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-base font-semibold">{selected}</h2>
                  <p>{selectedAgent?.display_name ?? selected}</p>
                  <p>Status {selectedAgent?.status ?? "unavailable"}</p>
                  <p>{deskHealth(selectedAgent, snapshot.ready)}</p>
                  <p>Verified trading activity: {snapshot.verified}</p>
                  <p>No order is sent. Trading denied. Simulated.</p>
                </div>
                <button type="button" className="vx-btn" onClick={() => setDetailOpen(false)}>
                  Close detail
                </button>
              </div>
              <h3 className="mt-3 font-semibold">Task history</h3>
              <ul className="mt-1 space-y-1 text-muted">
                {taskHistory(snapshot.audit).map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
              <p className="mt-2 text-muted">{snapshot.notes ?? "Current focus is not verified."}</p>
              <form
                className="mt-3 space-y-2"
                onSubmit={(event) => {
                  event.preventDefault();
                  const text = draft.trim();
                  if (!text) {
                    return;
                  }
                  setNotes((current) => [...current, text]);
                  setDraft("");
                }}
              >
                <label htmlFor="sanctum-note" className="block text-muted">
                  Local note. No model is called. Nothing is sent to a provider.
                </label>
                <textarea
                  id="sanctum-note"
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  className="vx-field h-16"
                />
                <button type="submit" className="vx-btn">
                  Save local note
                </button>
              </form>
              <ul className="mt-2 space-y-1">
                {notes.map((note, index) => (
                  <li key={`${index}-${note}`}>{note}</li>
                ))}
              </ul>
            </section>
          ) : null}
        </div>
        <aside className="flex flex-col gap-3 overflow-auto border-l border-line bg-[#0c1210] p-3 text-sm">
          <div>
            <h1 className="text-base font-semibold">Sanctum — Sky View</h1>
            <p className="text-xs text-muted">Live Agency Operations</p>
          </div>
          <section aria-label="Agency status" className="vx-card">
            <p className="text-xs text-muted">Agency Status</p>
            <p className="mt-1 font-semibold text-danger">
              {snapshot.loaded ? agencyStatus(snapshot.ready) : "Loading"}
            </p>
            <p className="mt-1 text-xs text-muted">No order is sent. Trading denied. Simulated.</p>
          </section>
          {snapshot.loaded && !snapshot.ready ? (
            <p className="vx-alert" role="alert">
              Agent registry is unavailable. No desk was invented. No order was sent.
            </p>
          ) : null}
          {snapshot.loaded && snapshot.futuresAlert ? (
            <p className="vx-alert" role="alert">
              Futures posture is unavailable. No order was sent.
            </p>
          ) : null}
          <section aria-label="Agency counts" className="vx-card space-y-2">
            <div className="flex items-baseline justify-between gap-3">
              <span>Agents present</span>
              <span className="font-semibold">{counts.value}</span>
            </div>
            <p className="text-xs text-muted">{counts.detail}</p>
            <div className="flex items-baseline justify-between gap-3">
              <span>Running</span>
              <span className="font-semibold">{runningLabel}</span>
            </div>
            <div className="flex items-baseline justify-between gap-3">
              <span>Active tasks</span>
              <span className="font-semibold">not verified</span>
            </div>
            <div className="flex items-baseline justify-between gap-3">
              <span>Trades (Paper)</span>
              <span className="font-semibold">{snapshot.trades.value}</span>
            </div>
            <p className="text-xs text-muted">{paperLine}</p>
            {paperLine === snapshot.trades.detail ? null : (
              <p className="text-xs text-muted">{snapshot.trades.detail}</p>
            )}
            <div className="flex items-baseline justify-between gap-3">
              <span>Alerts</span>
              <span className="font-semibold">{snapshot.alerts}</span>
            </div>
          </section>
          {rail === "agents" ? (
            <section aria-label="Agent list" className="space-y-1">
              {FLOOR_ORDER.map((code) => (
                <button
                  key={code}
                  type="button"
                  className="block w-full rounded-md px-2 py-1 text-left hover:bg-panel-2"
                  onClick={() => {
                    setSelected(code);
                    setDetailOpen(true);
                    gameRef.current?.follow(code);
                  }}
                >
                  Show {code}
                </button>
              ))}
            </section>
          ) : null}
          {rail === "boardroom" ? (
            <section aria-label="Boardroom schedule" className="space-y-2 text-xs text-muted">
              <p>Wednesday {formatLongDate(wednesday)}. Local schedule, not a booked meeting.</p>
              {snapshot.reminders ? (
                <p>
                  Accounting close {snapshot.reminders.close}. Payout review {snapshot.reminders.review}. DayPilot
                  event was not created. Meeting time is unconfirmed.
                </p>
              ) : (
                <p>Close and review dates are unavailable. No meeting was booked.</p>
              )}
              <div className="flex gap-2">
                <button type="button" className="vx-btn" onClick={() => gameRef.current?.gather()}>
                  Gather in the boardroom
                </button>
                <button type="button" className="vx-btn" onClick={() => gameRef.current?.returnToDesks()}>
                  Return to desks
                </button>
              </div>
            </section>
          ) : null}
          {rail === "logs" ? (
            <section aria-label="Logs">
              <p className="text-xs text-muted">{realtimeNote}</p>
              <ul className="mt-2 space-y-1 text-xs">
                {taskHistory(snapshot.audit).map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </section>
          ) : null}
          <section aria-label="Live activity feed" className="min-h-0 flex-1">
            <h2 className="text-xs font-semibold text-muted">Live Activity Feed</h2>
            <ul className="mt-2 max-h-40 space-y-2 overflow-auto text-xs">
              {feed.map((line) => (
                <li key={line} className="flex gap-2">
                  <span aria-hidden="true" className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-jade" />
                  <span>{line}</span>
                </li>
              ))}
            </ul>
            <p className="mt-2 text-[11px] text-muted">
              {feedMode === "realtime" ? "Supabase channel subscribed. Registry status still comes from FastAPI. " : null}
              {realtimeNote}
            </p>
          </section>
          <section aria-label="Camera controls" className="space-y-2">
            <h2 className="text-xs font-semibold text-muted">Camera Controls</h2>
            <div className="grid grid-cols-4 gap-1">
              <button type="button" aria-label="Pan up" className="vx-btn" onClick={() => gameRef.current?.panBy(0, -80)}>
                ↑
              </button>
              <button type="button" aria-label="Pan left" className="vx-btn" onClick={() => gameRef.current?.panBy(-80, 0)}>
                ←
              </button>
              <button type="button" aria-label="Pan right" className="vx-btn" onClick={() => gameRef.current?.panBy(80, 0)}>
                →
              </button>
              <button type="button" aria-label="Pan down" className="vx-btn" onClick={() => gameRef.current?.panBy(0, 80)}>
                ↓
              </button>
              <button type="button" aria-label="Zoom out" className="vx-btn" onClick={() => gameRef.current?.zoomBy(0.85)}>
                −
              </button>
              <button type="button" aria-label="Zoom in" className="vx-btn" onClick={() => gameRef.current?.zoomBy(1.15)}>
                +
              </button>
              <button type="button" aria-label="Fit the floor" className="vx-btn col-span-2" onClick={() => setCamera("sky", "sky")}>
                Fit
              </button>
            </div>
            <div className="grid grid-cols-2 gap-1">
              <button type="button" className="vx-btn" onClick={() => setCamera("sky", "sky")}>
                Full Floor
              </button>
              <button type="button" className="vx-btn" onClick={() => setCamera("center")}>
                Center
              </button>
              <button type="button" className="vx-btn" onClick={() => setCamera("meeting", "boardroom")}>
                Meeting
              </button>
              <button
                type="button"
                className="vx-btn"
                title="Frame the trading desks. No order is sent."
                onClick={() => setCamera("trading")}
              >
                Trading
              </button>
            </div>
          </section>
          <section aria-label="Floor zones">
            <h2 className="text-xs font-semibold text-muted">Floor Zones</h2>
            <ul className="mt-2 space-y-1 text-xs">
              {ZONES.map((zone) => (
                <li key={zone.label} className="flex items-center gap-2">
                  <span aria-hidden="true" className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: zone.colour }} />
                  {zone.label}
                </li>
              ))}
            </ul>
          </section>
        </aside>
      </div>
      <footer className="flex shrink-0 items-center gap-4 overflow-x-auto border-t border-line bg-[#0c1210] px-4 py-3">
        <div className="grid h-16 w-16 shrink-0 place-items-center overflow-hidden rounded-md border border-jade/40 bg-obsidian">
          <Portrait code={selected} />
        </div>
        <div className="min-w-36">
          <p className="font-semibold">{selected}</p>
          <p className="text-xs text-muted">{selectedAgent?.display_name ?? "Registry name not loaded"}</p>
          <p className="mt-1 text-xs text-danger">{selectedAgent?.status ?? "unavailable"}</p>
        </div>
        <div className="min-w-40 border-l border-line pl-4">
          <p className="text-[11px] text-muted">Current Focus</p>
          <p className="max-w-xs text-xs">{snapshot.notes ?? "not verified"}</p>
        </div>
        <div className="min-w-44 border-l border-line pl-4">
          <p className="text-[11px] text-muted">Next Event</p>
          <p className="text-sm">Wednesday Boardroom</p>
          <p className="text-xs text-muted">{formatLongDate(wednesday)}</p>
          <p className="text-[11px] text-muted">Local schedule, not a booked meeting.</p>
        </div>
        <div className="min-w-48 border-l border-line pl-4">
          <p className="text-[11px] text-muted">System Health</p>
          <p className="text-xs">{snapshot.health}</p>
        </div>
        <div className="min-w-32 border-l border-line pl-4">
          <p className="text-[11px] text-muted">AI Agents</p>
          <p className="text-sm">{counts.detail}</p>
        </div>
        <div className="min-w-40 border-l border-line pl-4">
          <p className="text-[11px] text-muted">Trading Mode</p>
          <p className="text-sm">Simulation (Paper)</p>
          <p className="text-[11px] text-muted">No order is sent. Simulated.</p>
        </div>
        <Link to="/settings" className="vx-btn ml-auto" aria-label="Settings">
          Settings
        </Link>
      </footer>
    </div>
  );
}
