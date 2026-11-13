import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { apiGet } from "../api/client";
import {
  AGENT_CODES,
  DENIED_TOOLS,
  type AgentCode,
  type AgentDesk,
  type AgentListResponse,
  type DeskDetail,
} from "../api/types";
import { AGENCY_NOTICE } from "../content";

const REGISTRY_DOWN = "The agent registry is unavailable. No desk was invented.";
const DESK_HIDDEN = "This desk cannot be shown. Nothing was enabled.";
const DESK_MISSING = "That desk is not in the registry. Nothing was enabled.";

type RegistryState =
  | { status: "loading" }
  | { status: "unavailable" }
  | { status: "ready"; agents: AgentDesk[] };

type DetailState =
  | { status: "loading" }
  | { status: "missing" }
  | { status: "unavailable" }
  | { status: "ready"; desk: DeskDetail };

function isDesk(value: AgentDesk): boolean {
  return (
    (AGENT_CODES as readonly string[]).includes(value.code) &&
    value.display_name.trim().length > 0 &&
    value.desk.trim().length > 0 &&
    (value.status === "disabled" || value.status === "paused" || value.status === "enabled") &&
    value.paper_only === true &&
    value.can_submit_orders === false &&
    value.can_sign === false &&
    value.can_transfer_funds === false &&
    value.holds_credentials === false &&
    value.permission_effect === "deny"
  );
}

function isRegistry(value: AgentListResponse): boolean {
  return (
    value.source === "local_registry" &&
    value.trading_rights === "denied" &&
    value.execution_permitted === false &&
    value.order_submitted === false &&
    value.agents.length === AGENT_CODES.length &&
    value.agents.every(isDesk)
  );
}

function isKnownCode(code: string): code is AgentCode {
  return (AGENT_CODES as readonly string[]).includes(code);
}

function isDetail(value: DeskDetail): boolean {
  return (
    isDesk(value) &&
    value.notes.trim().length > 0 &&
    value.running === false &&
    value.can_enable === false &&
    value.source === "local_registry" &&
    value.trading_rights === "denied" &&
    value.execution_permitted === false &&
    value.order_submitted === false &&
    value.tools.length === DENIED_TOOLS.length &&
    value.tools.every(
      (tool, index) => tool.tool_name === DENIED_TOOLS[index] && tool.effect === "deny",
    )
  );
}

function DeskList() {
  const [registry, setRegistry] = useState<RegistryState>({ status: "loading" });

  useEffect(() => {
    document.title = "Agency · Veytrix";
  }, []);

  useEffect(() => {
    let cancelled = false;
    apiGet<AgentListResponse>("/api/v1/agents")
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setRegistry(
          isRegistry(payload) ? { status: "ready", agents: payload.agents } : { status: "unavailable" },
        );
      })
      .catch(() => {
        if (!cancelled) {
          setRegistry({ status: "unavailable" });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="vx-page">
      <div>
        <p className="text-sm font-semibold text-jade">Denied</p>
        <h1 className="vx-title">Agency</h1>
        <p className="vx-lede">{AGENCY_NOTICE}</p>
      </div>
      <section aria-label="Desks" className="space-y-3">
        <h2 className="vx-section-title">Desks</h2>
        {registry.status === "loading" ? <p className="text-sm text-muted">Loading desks.</p> : null}
        {registry.status === "unavailable" ? <p className="text-sm text-muted">{REGISTRY_DOWN}</p> : null}
        {registry.status === "ready" ? (
          <table className="w-full border-collapse text-sm">
            <caption className="sr-only">Desks. Trading rights are denied.</caption>
            <thead>
              <tr className="border-b border-line text-left text-muted">
                <th className="py-2 pr-4 font-medium">Desk</th>
                <th className="py-2 pr-4 font-medium">Name</th>
                <th className="py-2 pr-4 font-medium">Status</th>
                <th className="py-2 font-medium">Rights</th>
              </tr>
            </thead>
            <tbody>
              {registry.agents.map((agent) => (
                <tr key={agent.code} className="border-b border-line">
                  <td className="py-2 pr-4">
                    <Link to={`/agency/${agent.code}`}>{agent.code}</Link>
                  </td>
                  <td className="py-2 pr-4">{agent.display_name}</td>
                  <td className="py-2 pr-4">{agent.status}</td>
                  <td className="py-2">Denied</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
      </section>
    </div>
  );
}

function DeskRead({ code }: { code: string }) {
  const [detail, setDetail] = useState<DetailState>({ status: "loading" });

  useEffect(() => {
    document.title = "Agency · Veytrix";
  }, []);

  useEffect(() => {
    if (!isKnownCode(code)) {
      setDetail({ status: "missing" });
      return;
    }
    let cancelled = false;
    apiGet<DeskDetail>(`/api/v1/agency/desks/${code}`)
      .then((payload) => {
        if (cancelled) {
          return;
        }
        if (!isDetail(payload) || payload.code !== code) {
          setDetail({ status: "unavailable" });
          return;
        }
        setDetail({ status: "ready", desk: payload });
      })
      .catch(() => {
        if (!cancelled) {
          setDetail({ status: "unavailable" });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [code]);

  const desk = detail.status === "ready" ? detail.desk : null;

  return (
    <div className="vx-page">
      <div>
        <p className="text-sm font-semibold text-jade">Denied</p>
        <h1 className="vx-title">Desk</h1>
        <p className="vx-lede">{AGENCY_NOTICE}</p>
        <p className="mt-3 text-sm">
          <Link to="/agency">All desks</Link>
        </p>
      </div>
      {detail.status === "loading" ? <p className="text-sm text-muted">Loading this desk.</p> : null}
      {detail.status === "missing" ? <p className="text-sm text-muted">{DESK_MISSING}</p> : null}
      {detail.status === "unavailable" ? (
        <p className="text-sm text-muted">{DESK_HIDDEN}</p>
      ) : null}
      {desk ? (
        <section aria-label="Desk detail" className="max-w-xl space-y-4 text-sm">
          <h2 className="vx-section-title">{desk.code}</h2>
          <p>{desk.display_name}</p>
          <p>Status {desk.status}</p>
          <p>Rights denied. This desk is not running.</p>
          <p>{desk.notes}</p>
          <table className="w-full border-collapse">
            <caption className="sr-only">Denied tools. None of these can be turned on here.</caption>
            <thead>
              <tr className="border-b border-line text-left text-muted">
                <th className="py-2 pr-4 font-medium">Tool</th>
                <th className="py-2 font-medium">Effect</th>
              </tr>
            </thead>
            <tbody>
              {desk.tools.map((tool) => (
                <tr key={tool.tool_name} className="border-b border-line">
                  <td className="py-2 pr-4 font-mono">{tool.tool_name}</td>
                  <td className="py-2">Deny</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : null}
    </div>
  );
}

export function AgencyPage() {
  const { code } = useParams();
  if (code) {
    return <DeskRead code={code} />;
  }
  return <DeskList />;
}
