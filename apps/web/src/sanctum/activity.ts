import {
  AGENT_CODES,
  DENIED_TOOLS,
  type AgentCode,
  type AgentDesk,
  type AgentListResponse,
  type DeskDetail,
  type FuturesPostureResponse,
} from "../api/types";

export type DeskPose = "idle" | "working" | "error";

export function isDesk(value: AgentDesk): boolean {
  return (
    (AGENT_CODES as readonly string[]).includes(value.code) &&
    value.display_name.trim().length > 0 &&
    value.desk.trim().length > 0 &&
    (value.status === "disabled" || value.status === "paused") &&
    value.paper_only === true &&
    value.can_submit_orders === false &&
    value.can_sign === false &&
    value.can_transfer_funds === false &&
    value.holds_credentials === false &&
    value.permission_effect === "deny"
  );
}

export function isRegistry(value: AgentListResponse): boolean {
  return (
    value.source === "local_registry" &&
    value.trading_rights === "denied" &&
    value.execution_permitted === false &&
    value.order_submitted === false &&
    value.agents.length === AGENT_CODES.length &&
    AGENT_CODES.every((code) => value.agents.some((agent) => agent.code === code && isDesk(agent)))
  );
}

export function isDeskDetail(value: DeskDetail, code: AgentCode): boolean {
  return (
    isDesk(value) &&
    value.code === code &&
    value.notes.trim().length > 0 &&
    value.running === false &&
    value.can_enable === false &&
    value.source === "local_registry" &&
    value.trading_rights === "denied" &&
    value.execution_permitted === false &&
    value.order_submitted === false &&
    value.tools.length === DENIED_TOOLS.length &&
    value.tools.every((tool, index) => tool.tool_name === DENIED_TOOLS[index] && tool.effect === "deny")
  );
}

export function isFuturesPosture(value: FuturesPostureResponse): boolean {
  return (
    value.desk === "FUTURES-01" &&
    value.status === "disabled" &&
    value.symbols[0] === "MES" &&
    value.symbols[1] === "MNQ" &&
    value.topstep_automation === "disabled" &&
    value.topstep_account === "not_connected" &&
    value.orders === "absent" &&
    value.market_data === "not_read" &&
    value.can_enable === false &&
    value.execution_permitted === false &&
    value.order_submitted === false &&
    value.broker_called === false &&
    value.source === "local_posture" &&
    value.note.length > 0
  );
}

export function poseFor(agent: AgentDesk | undefined, reachable: boolean): DeskPose {
  if (!reachable || !agent || !isDesk(agent)) {
    return "error";
  }
  if (agent.status === "disabled" || agent.status === "paused") {
    return "idle";
  }
  return "error";
}

type BroadcastFields = {
  code?: unknown;
  status?: unknown;
  trading_rights?: unknown;
  execution_permitted?: unknown;
  order_submitted?: unknown;
  running?: unknown;
};

function broadcastFields(payload: unknown): BroadcastFields | null {
  if (typeof payload !== "object" || payload === null) {
    return null;
  }
  const record = payload as BroadcastFields & { payload?: unknown };
  if (typeof record.payload === "object" && record.payload !== null) {
    return record.payload as BroadcastFields;
  }
  return record;
}

/** A realtime payload cannot invent a trade. Unexpected permission becomes an error pose. */
export function poseFromBroadcast(payload: unknown): { code: AgentCode; pose: DeskPose } | null {
  const fields = broadcastFields(payload);
  if (!fields || typeof fields.code !== "string") {
    return null;
  }
  if (!(AGENT_CODES as readonly string[]).includes(fields.code)) {
    return null;
  }
  const code = fields.code as AgentCode;
  if (fields.execution_permitted === true || fields.order_submitted === true) {
    return { code, pose: "error" };
  }
  if (
    fields.running === true &&
    fields.execution_permitted === false &&
    fields.order_submitted === false &&
    fields.trading_rights === "denied"
  ) {
    return { code, pose: "working" };
  }
  if (
    (fields.status === "disabled" || fields.status === "paused") &&
    fields.execution_permitted === false &&
    fields.trading_rights === "denied"
  ) {
    return { code, pose: "idle" };
  }
  return null;
}

export function deskHealth(agent: AgentDesk | null, reachable: boolean): string {
  if (!reachable || !agent) {
    return "Unavailable. This is not a broker balance.";
  }
  return "Idle. Trading denied. This is not a broker balance.";
}

export function agencyStatus(ready: boolean): string {
  return ready ? "Trading denied" : "Unavailable";
}

export function agentStat(agents: AgentDesk[] | null): { value: string; detail: string } {
  if (!agents) {
    return { value: "not verified", detail: "Registry unread" };
  }
  const running = agents.filter((agent) => agent.status !== "disabled" && agent.status !== "paused").length;
  return { value: String(agents.length), detail: `${agents.length} present, ${running} running` };
}

export function paperTradeStat(value: unknown): { value: string; detail: string } {
  if (typeof value !== "object" || value === null) {
    return { value: "not verified", detail: "Ledger unread" };
  }
  const record = value as {
    local_orders?: unknown;
    broker_read?: unknown;
    reconciled?: unknown;
    rows?: unknown;
  };
  const rows = Array.isArray(record.rows) ? record.rows : [];
  const confirmed = rows.some(
    (row) =>
      typeof row === "object" &&
      row !== null &&
      (row as { broker_status?: unknown }).broker_status === "broker_confirmed",
  );
  if (confirmed) {
    return { value: "broker-confirmed", detail: "A reconciliation row says broker-confirmed." };
  }
  if (
    record.broker_read === "absent" &&
    record.reconciled === false &&
    typeof record.local_orders === "number"
  ) {
    return {
      value: String(record.local_orders),
      detail: "Local ledger only. None broker-confirmed.",
    };
  }
  return { value: "not verified", detail: "Ledger unread" };
}

export function verifiedTrading(value: unknown): string {
  const stat = paperTradeStat(value);
  return stat.value === "broker-confirmed" ? "broker-confirmed" : "none verified";
}

export function systemHealth(healthOk: boolean, liveBrokerDisabled: boolean): string {
  if (!healthOk) {
    return "not verified";
  }
  if (liveBrokerDisabled) {
    return "API reachable. Live broker disabled. Not a percentage.";
  }
  return "API reachable. Not a percentage.";
}

export type FeedInput = {
  agents: { code: string; status: string }[] | null;
  futuresNote: string | null;
  audit: { created_at: string; action: string }[] | null;
};

export function activityFeed(input: FeedInput): string[] {
  const lines: string[] = [];
  if (input.futuresNote) {
    lines.push(input.futuresNote);
  }
  for (const event of input.audit ?? []) {
    lines.push(`${event.created_at} ${event.action}. No order submitted.`);
  }
  if (!input.agents) {
    lines.push("Desk activity is not verified.");
  } else {
    for (const agent of input.agents) {
      lines.push(`${agent.code} is ${agent.status}. Idle. Activity is not verified.`);
    }
  }
  lines.push("Verified trading activity: none verified.");
  return lines;
}

export function taskHistory(events: { created_at: string; action: string }[] | null): string[] {
  if (!events) {
    return ["Task history is unavailable. No task was invented."];
  }
  if (events.length === 0) {
    return ["No per-desk task history is stored. The size audit log is empty."];
  }
  return events
    .slice(0, 6)
    .map((event) => `${event.created_at} ${event.action}. No order submitted.`);
}
