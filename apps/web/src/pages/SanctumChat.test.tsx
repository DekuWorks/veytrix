import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiGet, apiPost } from "../api/client";
import { AGENT_CODES, type AgentCode } from "../api/types";
import { AppRoutes } from "../App";
import type { CommsMessage, Conversation } from "../comms/types";

vi.mock("../api/client", () => {
  class MockApiError extends Error {
    status: number;
    body: unknown;
    constructor(status: number, body: unknown) {
      super(`status ${status}`);
      this.status = status;
      this.body = body;
    }
  }
  return {
    ApiError: MockApiError,
    apiGet: vi.fn(),
    apiPost: vi.fn(),
    apiPatch: vi.fn(),
    errorDetail: (body: unknown) =>
      typeof body === "object" && body !== null && "detail" in body
        ? String((body as { detail: unknown }).detail)
        : null,
  };
});

const NAMES: Record<AgentCode, string> = {
  "SUPERVISOR-01": "Roads",
  "DAY-01": "Dayvid",
  "STOCK-01": "Vex",
  "CRYPTO-01": "Nyx",
  "DEFI-01": "Cipher",
  "ETF-01": "Lyra",
  "FUTURES-01": "Futures",
  "RESEARCH-01": "Astra",
  "RISK-01": "Aegis",
  "TREASURY-01": "Midas",
};

function msg(over: Partial<CommsMessage>): CommsMessage {
  return {
    message_id: "m",
    conversation_id: "c-direct",
    seq: 1,
    thread_id: null,
    sender_id: "HUMAN",
    sender_name: "You",
    sender_kind: "human",
    recipient_ids: [],
    kind: "chat",
    origin: "human",
    origin_label: "you",
    timestamp: "2026-11-09T12:00:00Z",
    correlation_id: "c",
    task_id: null,
    decision_id: null,
    tool_call_id: null,
    content: "hi",
    status: "delivered",
    visibility: "conversation",
    citations: [],
    meta: {},
    ...over,
  };
}

function conv(over: Partial<Conversation>): Conversation {
  return {
    conversation_id: "c-direct",
    kind: "direct",
    title: "Desk",
    topic: "t",
    status: "open",
    pinned: false,
    created_by: "human",
    owner_id: null,
    max_rounds: 0,
    max_messages: 500,
    created_at: "2026-11-09T12:00:00Z",
    updated_at: "2026-11-09T12:00:00Z",
    closed_at: null,
    message_count: 0,
    unread: 0,
    members: [],
    agenda: null,
    last_message: null,
    ...over,
  };
}

const registry = AGENT_CODES.map((code) => ({
  code,
  display_name: `${NAMES[code]} desk`,
  desk: "desk",
  status: "enabled",
  paper_only: true,
  can_submit_orders: false,
  can_sign: false,
  can_transfer_funds: false,
  holds_credentials: false,
  permission_effect: "deny",
}));

type Backend = {
  stored: Record<string, CommsMessage[]>;
  conversations: Conversation[];
  chatDown: boolean;
};

let backend: Backend;
let fetchMock: ReturnType<typeof vi.fn>;

function install() {
  vi.mocked(apiGet).mockImplementation((path: string) => {
    if (path === "/api/v1/agents") {
      return Promise.resolve({
        agents: registry,
        source: "local_registry",
        trading_rights: "denied",
        execution_permitted: false,
        order_submitted: false,
      });
    }
    if (path.startsWith("/api/v1/comms/flags")) {
      return Promise.resolve({
        flags: { agent_chat: true, group_chat: true, autonomous_discussions: false, voice_chat: false, live_execution: false },
        realtime: "not_configured",
        model: "not_configured",
        note: "",
      });
    }
    if (path.startsWith("/api/v1/comms/feed")) {
      return Promise.resolve({ realtime: "not_configured", messages: [] });
    }
    if (path.startsWith("/api/v1/comms/conversations?") || path === "/api/v1/comms/conversations") {
      return Promise.resolve({ conversations: backend.conversations });
    }
    const match = /\/api\/v1\/comms\/conversations\/([^/]+)\/messages/.exec(path);
    if (match) {
      return Promise.resolve({
        conversation_id: match[1],
        messages: backend.stored[match[1]] ?? [],
        has_more: false,
        next_after_seq: 0,
      });
    }
    return Promise.reject(new Error(path));
  });
  vi.mocked(apiPost).mockImplementation((path: string, body: unknown) => {
    const payload = body as Record<string, unknown>;
    if (path === "/api/v1/comms/conversations" && payload.kind === "direct") {
      if (backend.chatDown) {
        return Promise.reject(new ApiError(503, { detail: "Conversation store is unavailable." }));
      }
      const code = payload.agent_code as string;
      const found = backend.conversations.find((c) => c.conversation_id === `c-${code}`);
      const created = found ?? conv({ conversation_id: `c-${code}`, title: NAMES[code as AgentCode] });
      if (!found) {
        backend.conversations.push(created);
        backend.stored[created.conversation_id] = [];
      }
      return Promise.resolve({ conversation: created });
    }
    const send = /\/api\/v1\/comms\/conversations\/([^/]+)\/messages$/.exec(path);
    if (send) {
      const id = send[1];
      const code = id.replace("c-", "") as AgentCode;
      const seq = (backend.stored[id]?.length ?? 0) + 1;
      const human = msg({ message_id: `h-${seq}`, conversation_id: id, seq, content: String(payload.content) });
      const reply = msg({
        message_id: `r-${seq}`,
        conversation_id: id,
        seq: seq + 1,
        sender_id: code,
        sender_name: NAMES[code],
        sender_kind: "agent",
        kind: "reply",
        origin: "tool_verified",
        origin_label: "verified from local records",
        content: `${NAMES[code]}, risk desk. Enabled, English. Reading the paper risk policy.`,
        citations: [{ source: "registry", ref: `private.agents/${code}`, label: "Registry status is enabled.", as_of: null, untrusted: false }],
      });
      backend.stored[id] = [...(backend.stored[id] ?? []), human, reply];
      return Promise.resolve({
        conversation: conv({ conversation_id: id, title: NAMES[code], message_count: seq + 1 }),
        messages: [human, reply],
        duplicate: false,
        held: null,
        errors: [],
        realtime: "not_configured",
      });
    }
    if (path === "/api/v1/comms/discussions") {
      const id = "c-discussion";
      const members = ["SUPERVISOR-01", "STOCK-01", "RISK-01"].map((code) => ({
        member_id: code,
        member_name: NAMES[code as AgentCode],
        member_kind: "agent" as const,
        role: "participant",
        last_read_seq: 0,
      }));
      const rows = [
        msg({ message_id: "d1", conversation_id: id, seq: 1, content: String(payload.topic) }),
        msg({ message_id: "d2", conversation_id: id, seq: 2, sender_id: "SUPERVISOR-01", sender_name: "Roads", sender_kind: "agent", kind: "notice", origin: "scripted", content: "Topic opened. Rounds: 2." }),
        msg({ message_id: "d3", conversation_id: id, seq: 3, sender_id: "STOCK-01", sender_name: "Vex", sender_kind: "agent", kind: "claim", origin: "simulated", content: "Vex on the topic. Evidence: supported.", meta: { position: "supported" } }),
        msg({ message_id: "d4", conversation_id: id, seq: 4, sender_id: "RISK-01", sender_name: "Aegis", sender_kind: "agent", kind: "objection", origin: "simulated", content: "Aegis objects: one source cannot confirm itself." }),
      ];
      backend.stored[id] = rows;
      const created = conv({ conversation_id: id, kind: "discussion", title: "Discussion · topic", status: "closed", members, message_count: 4 });
      backend.conversations.unshift(created);
      return Promise.resolve({ conversation: created, messages: rows, duplicate: false, held: null, errors: [], realtime: "not_configured" });
    }
    return Promise.reject(new Error(path));
  });
  fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input).replace(/^https?:\/\/[^/]+/, "");
    const payload = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
    const send = /\/conversations\/([^/]+)\/messages\/stream$/.exec(path);
    if (!send) {
      return new Response("missing", { status: 404 });
    }
    const id = send[1];
    const code = id.replace("c-", "") as AgentCode;
    const seq = (backend.stored[id]?.length ?? 0) + 1;
    const human = msg({ message_id: `h-${seq}`, conversation_id: id, seq, content: String(payload.content) });
    const reply = msg({
      message_id: `r-${seq}`,
      conversation_id: id,
      seq: seq + 1,
      sender_id: code,
      sender_name: NAMES[code],
      sender_kind: "agent",
      kind: "reply",
      origin: "tool_verified",
      origin_label: "verified from local records",
      content: `${NAMES[code]}, risk desk. Enabled, English. Reading the paper risk policy.`,
      citations: [{ source: "registry", ref: `private.agents/${code}`, label: "Registry status is enabled.", as_of: null, untrusted: false }],
    });
    backend.stored[id] = [...(backend.stored[id] ?? []), human, reply];
    const result = {
      conversation: conv({ conversation_id: id, title: NAMES[code], message_count: seq + 1 }),
      messages: [human, reply],
      duplicate: false,
      held: null,
      errors: [],
      realtime: "not_configured",
      execution_permitted: false,
      order_submitted: false,
    };
    const raw = `event: chunk\ndata: ${JSON.stringify({ text: "Aegis", sender: code })}\n\nevent: done\ndata: ${JSON.stringify(result)}\n\n`;
    return new Response(raw, { status: 200, headers: { "Content-Type": "text/event-stream" } });
  });
  vi.stubGlobal("fetch", fetchMock);
}

function renderSanctum() {
  return render(
    <MemoryRouter initialEntries={["/sanctum"]}>
      <AppRoutes />
    </MemoryRouter>,
  );
}

const user = {
  click: async (element: Element) => {
    fireEvent.click(element);
  },
  type: async (element: Element, text: string) => {
    fireEvent.change(element, { target: { value: text } });
  },
};

describe("sanctum chat", () => {
  beforeEach(() => {
    backend = { stored: {}, conversations: [], chatDown: false };
    vi.mocked(apiGet).mockReset();
    vi.mocked(apiPost).mockReset();
    install();
  });

  it("opens a chat, sends a question, shows the stored reply with its origin and sources, and the avatar speaks it", async () => {
    renderSanctum();
    await user.click(screen.getByRole("button", { name: /Aegis\s*Risk desk/ }));
    const dialog = await screen.findByRole("dialog", { name: "Chat with Aegis" });
    const box = await within(dialog).findByRole("textbox", { name: "Message Aegis" });
    await user.type(box, "What are you working on?");
    await user.click(within(dialog).getByRole("button", { name: "Send" }));
    const log = await within(dialog).findByRole("log", { name: "Transcript with Aegis" });
    expect(await within(log).findByText("What are you working on?")).toBeInTheDocument();
    expect(await within(log).findByText(/Aegis, risk desk\. Enabled, English/)).toBeInTheDocument();
    expect(within(log).getByText("verified")).toBeInTheDocument();
    expect(within(log).getByText("Sources (1)")).toBeInTheDocument();
    const streamed = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/messages/stream"));
    expect(JSON.parse(String((streamed?.[1] as RequestInit | undefined)?.body))).toMatchObject({
      content: "What are you working on?",
    });
    // The bubble above the avatar is the stored message, not a generated line.
    const bubble = await waitFor(
      () => {
        const found = document.querySelector('.thought.live[data-message-id="r-1"]');
        expect(found).not.toBeNull();
        return found as HTMLElement;
      },
      { timeout: 3000 },
    );
    expect(bubble.textContent).toContain("Aegis, risk desk.");
    expect(bubble.textContent).toContain("Enabled, English.");
    expect(bubble.textContent).not.toContain("Reading the paper risk policy.");
    expect(bubble.textContent).toContain("verified");
    expect(document.body.textContent).not.toMatch(/deterministic\. No order/i);
  });

  it("sends a quick question without typing", async () => {
    renderSanctum();
    await user.click(screen.getByRole("button", { name: /Vex\s*Stock desk/ }));
    const dialog = await screen.findByRole("dialog", { name: "Chat with Vex" });
    await user.click(await within(dialog).findByRole("button", { name: "Show sources" }));
    expect(await within(dialog).findByText("Show sources", { selector: "p" })).toBeInTheDocument();
  });

  it("gives an avatar with no stored message no speech at all", async () => {
    renderSanctum();
    await user.click(screen.getByRole("button", { name: /Lyra\s*ETF desk/ }));
    expect(await screen.findByText(/ETF-01 has no stored message yet/)).toBeInTheDocument();
    expect(document.querySelector(".thought")).toBeNull();
  });

  it("says chat is unavailable and offers a retry when the store is down", async () => {
    backend.chatDown = true;
    renderSanctum();
    await user.click(screen.getByRole("button", { name: /Midas\s*Treasury desk/ }));
    const dialog = await screen.findByRole("dialog", { name: "Chat with Midas" });
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("Conversation store is unavailable.");
    backend.chatDown = false;
    await user.click(within(dialog).getByRole("button", { name: "Retry" }));
    expect(await within(dialog).findByRole("textbox", { name: "Message Midas" })).toBeInTheDocument();
  });

  it("keeps the failed message and offers to retry it", async () => {
    renderSanctum();
    await user.click(screen.getByRole("button", { name: /Nyx\s*Crypto desk/ }));
    const dialog = await screen.findByRole("dialog", { name: "Chat with Nyx" });
    const box = await within(dialog).findByRole("textbox", { name: "Message Nyx" });
    const original = fetchMock.getMockImplementation()!;
    fetchMock.mockImplementationOnce(() => Promise.reject(new ApiError(429, { detail: "Too many messages. Slow down." })));
    await user.type(box, "latest bars");
    await user.click(within(dialog).getByRole("button", { name: "Send" }));
    expect(await within(dialog).findByText(/Too many messages/)).toBeInTheDocument();
    fetchMock.mockImplementation(original);
    await user.click(within(dialog).getByRole("button", { name: "Retry message" }));
    expect(await within(dialog).findByText(/Nyx, risk desk\. Enabled, English/)).toBeInTheDocument();
  });

  it.each(AGENT_CODES)("opens a direct conversation for %s from the agent list", async (code) => {
    renderSanctum();
    await user.click(screen.getByRole("button", { name: "Agent List" }));
    const row = (await screen.findAllByRole("button", { name: new RegExp(`${NAMES[code]}\\s*${code}`) }))[0];
    await user.click(row);
    expect(await screen.findAllByRole("dialog", { name: `Chat with ${NAMES[code]}` })).not.toHaveLength(0);
    await waitFor(() => {
      const open = vi.mocked(apiPost).mock.calls.find(
        ([path, body]) =>
          path === "/api/v1/comms/conversations" && (body as { agent_code?: string }).agent_code === code,
      );
      expect(open).toBeDefined();
    });
  });

  it("monitors conversations, starts a discussion, labels simulated turns, and replays the stored transcript", async () => {
    renderSanctum();
    await user.click(screen.getByRole("button", { name: "Conversations" }));
    expect(await screen.findByRole("heading", { name: "Conversation monitor" })).toBeInTheDocument();
    expect(screen.getByText(/Supabase Realtime is not configured/)).toBeInTheDocument();
    await user.type(screen.getByLabelText("Start a desk discussion"), "AAPL SMA crossover signals");
    await user.click(screen.getByRole("button", { name: "Start discussion" }));
    const log = await screen.findByRole("log", { name: /Transcript: Discussion/ });
    expect(await within(log).findByText("Vex on the topic. Evidence: supported.")).toBeInTheDocument();
    expect(within(log).getAllByText("simulated").length).toBe(2);
    expect(within(log).getByText("scripted")).toBeInTheDocument();
    expect(within(log).getByText("objection")).toBeInTheDocument();
    const post = vi.mocked(apiPost).mock.calls.find(([path]) => path === "/api/v1/comms/discussions");
    expect(post?.[1]).toMatchObject({ topic: "AAPL SMA crossover signals", rounds: 2, kind: "discussion" });

    await user.click(screen.getByRole("button", { name: "Replay transcript" }));
    const controls = screen.getByRole("group", { name: "Replay controls" });
    await user.click(within(controls).getByRole("button", { name: "Step" }));
    const bubble = await waitFor(
      () => {
        const found = document.querySelector(".thought.live.replay");
        expect(found).not.toBeNull();
        return found as HTMLElement;
      },
      { timeout: 3000 },
    );
    expect(bubble.textContent).toContain("Topic opened");
    expect(bubble.textContent).toContain("scripted");
    fireEvent.click(within(controls).getByRole("button", { name: "Restart" }));
  });

  it("offers no order, withdraw, or enable control anywhere in the chat", async () => {
    renderSanctum();
    await user.click(screen.getByRole("button", { name: /Roads\s*AI Commander/ }));
    await screen.findByRole("dialog", { name: "Chat with Roads" });
    expect(screen.queryByRole("button", { name: /place|submit|withdraw|transfer|go live|enable|sign/i })).not.toBeInTheDocument();
  });
});
