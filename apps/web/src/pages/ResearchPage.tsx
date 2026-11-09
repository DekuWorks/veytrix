import { useEffect, useState, type FormEvent } from "react";
import { apiDelete, apiGet, apiPost } from "../api/client";
import type {
  ResearchNoteListResponse,
  ResearchNoteResponse,
  SourceEventListResponse,
  SourceEventResponse,
} from "../api/types";
import { moveAgeMinutes } from "../market/moveAge";
import { NOTE_AGE_NOTE, noteAgeLine } from "../market/noteAge";
import { PUBLIC_LAG_NOTE, publicLagLine } from "../market/publicLag";

const NOTE_AGE_TICK_MS = 15_000;

const STORE_DOWN = "The research note store is unavailable. This note was not saved.";
const REMOVE_DOWN = "The research note store is unavailable. This note was not removed.";
const EVENT_HEADER =
  "Source events stored on this machine. Not news. Not a trading signal. No order is sent.";
const EVENT_EMPTY = "No source events recorded yet.";
const EVENT_STORE_DOWN = "The source event store is unavailable. This event was not saved.";
const EVENT_REMOVE_DOWN = "The source event store is unavailable. This event was not removed.";
const RECORD_AGE_NOTE =
  "Age of this record on this machine. Not news. Not a trading signal. No order is sent.";

function recordAgeLine(recordedAt: string, now: number): string {
  const minutes = moveAgeMinutes(recordedAt, now);
  if (minutes === null) {
    return "Record age is unavailable.";
  }
  const unit = minutes === 1 ? "minute" : "minutes";
  return `Record age ${minutes} ${unit}.`;
}

type ListState =
  | { status: "loading" }
  | { status: "unavailable" }
  | { status: "ready"; notes: ResearchNoteResponse[] };

type EventListState =
  | { status: "loading" }
  | { status: "unavailable" }
  | { status: "ready"; events: SourceEventResponse[] };

function isStoredNote(value: ResearchNoteResponse): boolean {
  return (
    value.title.trim().length > 0 &&
    value.title.length <= 120 &&
    value.body.trim().length > 0 &&
    value.body.length <= 4000 &&
    value.created_at.includes("T") &&
    !("symbol" in value) &&
    !("order_id" in value)
  );
}

function isSourceEvent(value: SourceEventResponse): boolean {
  return (
    value.title.trim().length > 0 &&
    value.title.length <= 120 &&
    value.source.trim().length > 0 &&
    value.source.length <= 200 &&
    value.event_time.includes("T") &&
    value.first_public_at.includes("T") &&
    value.recorded_at.includes("T") &&
    value.execution_permitted === false &&
    value.order_submitted === false &&
    !("symbol" in value) &&
    !("order_id" in value)
  );
}

export function ResearchPage() {
  const [list, setList] = useState<ListState>({ status: "loading" });
  const [events, setEvents] = useState<EventListState>({ status: "loading" });
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [eventTitle, setEventTitle] = useState("");
  const [source, setSource] = useState("");
  const [eventTime, setEventTime] = useState("");
  const [firstPublicAt, setFirstPublicAt] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [eventNotice, setEventNotice] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    document.title = "Research · Veytrix";
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), NOTE_AGE_TICK_MS);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    let cancelled = false;
    apiGet<ResearchNoteListResponse>("/api/v1/research/notes")
      .then((payload) => {
        if (cancelled) {
          return;
        }
        if (!Array.isArray(payload.notes) || !payload.notes.every(isStoredNote)) {
          setList({ status: "unavailable" });
          return;
        }
        setList({ status: "ready", notes: payload.notes });
      })
      .catch(() => {
        if (!cancelled) {
          setList({ status: "unavailable" });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    apiGet<SourceEventListResponse>("/api/v1/research/source-events")
      .then((payload) => {
        if (cancelled) {
          return;
        }
        if (!Array.isArray(payload.events) || !payload.events.every(isSourceEvent)) {
          setEvents({ status: "unavailable" });
          return;
        }
        setEvents({ status: "ready", events: payload.events });
      })
      .catch(() => {
        if (!cancelled) {
          setEvents({ status: "unavailable" });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextTitle = title.trim();
    const nextBody = body.trim();
    if (nextTitle.length === 0 || nextBody.length === 0 || list.status !== "ready") {
      return;
    }
    setNotice(null);
    try {
      const saved = await apiPost<ResearchNoteResponse>("/api/v1/research/notes", {
        title: nextTitle,
        body: nextBody,
      });
      if (!isStoredNote(saved)) {
        setNotice(STORE_DOWN);
        return;
      }
      setList({ status: "ready", notes: [saved, ...list.notes] });
      setTitle("");
      setBody("");
    } catch {
      setNotice(STORE_DOWN);
    }
  }

  async function removeNote(id: string) {
    if (list.status !== "ready") {
      return;
    }
    setNotice(null);
    try {
      await apiDelete(`/api/v1/research/notes/${id}`);
      setList({ status: "ready", notes: list.notes.filter((note) => note.id !== id) });
    } catch {
      setNotice(REMOVE_DOWN);
    }
  }

  async function onAddEvent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextTitle = eventTitle.trim();
    const nextSource = source.trim();
    const nextEventTime = eventTime.trim();
    const nextFirstPublic = firstPublicAt.trim();
    if (
      nextTitle.length === 0 ||
      nextSource.length === 0 ||
      nextEventTime.length === 0 ||
      nextFirstPublic.length === 0 ||
      events.status !== "ready"
    ) {
      return;
    }
    setEventNotice(null);
    try {
      const saved = await apiPost<SourceEventResponse>("/api/v1/research/source-events", {
        title: nextTitle,
        source: nextSource,
        event_time: nextEventTime,
        first_public_at: nextFirstPublic,
      });
      if (!isSourceEvent(saved)) {
        setEventNotice(EVENT_STORE_DOWN);
        return;
      }
      setEvents({ status: "ready", events: [saved, ...events.events] });
      setEventTitle("");
      setSource("");
      setEventTime("");
      setFirstPublicAt("");
    } catch {
      setEventNotice(EVENT_STORE_DOWN);
    }
  }

  async function removeEvent(id: string) {
    if (events.status !== "ready") {
      return;
    }
    setEventNotice(null);
    try {
      await apiDelete(`/api/v1/research/source-events/${id}`);
      setEvents({ status: "ready", events: events.events.filter((item) => item.id !== id) });
    } catch {
      setEventNotice(EVENT_REMOVE_DOWN);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Research</h1>
        <p className="mt-2 max-w-3xl text-sm text-muted">
          Research notes stored on this machine. Not instructions to trade. No order is sent.
        </p>
      </div>
      <form aria-label="Research notes" className="grid max-w-xl gap-4" onSubmit={onSubmit}>
        <label className="grid gap-1 text-sm">
          Title
          <input
            className="rounded-md border border-line bg-obsidian px-3 py-2"
            name="title"
            value={title}
            maxLength={120}
            onChange={(event) => setTitle(event.target.value)}
            required
          />
        </label>
        <label className="grid gap-1 text-sm">
          Note
          <textarea
            className="min-h-28 rounded-md border border-line bg-obsidian px-3 py-2"
            name="body"
            value={body}
            maxLength={4000}
            onChange={(event) => setBody(event.target.value)}
            required
          />
        </label>
        <button
          type="submit"
          className="w-fit rounded-md bg-jade px-4 py-2 text-sm font-semibold text-obsidian"
        >
          Add note
        </button>
      </form>
      {notice !== null ? (
        <p className="text-sm text-muted" role="alert">
          {notice}
        </p>
      ) : null}
      {list.status === "loading" ? (
        <p className="text-sm text-muted">Loading research notes.</p>
      ) : null}
      {list.status === "unavailable" ? (
        <p className="text-sm text-muted" role="alert">
          Research notes are unavailable. No note was invented.
        </p>
      ) : null}
      {list.status === "ready" && list.notes.length === 0 ? (
        <p className="text-sm text-muted">No research notes recorded yet.</p>
      ) : null}
      {list.status === "ready" && list.notes.length > 0 ? (
        <ul className="grid max-w-xl gap-3">
          {list.notes.map((note) => (
            <li key={note.id} className="rounded-md border border-line bg-panel p-4">
              <div className="flex items-start justify-between gap-3">
                <h2 className="text-base font-semibold">{note.title}</h2>
                <button
                  type="button"
                  className="rounded-md border border-line px-3 py-1 text-sm"
                  onClick={() => void removeNote(note.id)}
                >
                  Delete note
                </button>
              </div>
              <p className="mt-2 whitespace-pre-wrap text-sm">{note.body}</p>
              <p className="mt-2 text-xs text-muted">Recorded at {note.created_at}.</p>
              <p className="mt-2 text-sm">{noteAgeLine(note.created_at, now)}</p>
              <p className="text-sm text-warn">{NOTE_AGE_NOTE}</p>
            </li>
          ))}
        </ul>
      ) : null}
      <section aria-labelledby="source-events" className="space-y-4">
        <h2 id="source-events" className="text-lg font-semibold">
          {EVENT_HEADER}
        </h2>
        <form aria-label="Source events" className="grid max-w-xl gap-4" onSubmit={onAddEvent}>
          <label className="grid gap-1 text-sm">
            Title
            <input
              className="rounded-md border border-line bg-obsidian px-3 py-2"
              name="event-title"
              value={eventTitle}
              maxLength={120}
              onChange={(event) => setEventTitle(event.target.value)}
              required
            />
          </label>
          <label className="grid gap-1 text-sm">
            Source
            <input
              className="rounded-md border border-line bg-obsidian px-3 py-2"
              name="source"
              value={source}
              maxLength={200}
              onChange={(event) => setSource(event.target.value)}
              required
            />
          </label>
          <label className="grid gap-1 text-sm">
            Event time
            <input
              className="rounded-md border border-line bg-obsidian px-3 py-2"
              name="event-time"
              value={eventTime}
              onChange={(event) => setEventTime(event.target.value)}
              placeholder="2026-11-08T13:30:00Z"
              required
            />
          </label>
          <label className="grid gap-1 text-sm">
            First public time
            <input
              className="rounded-md border border-line bg-obsidian px-3 py-2"
              name="first-public-at"
              value={firstPublicAt}
              onChange={(event) => setFirstPublicAt(event.target.value)}
              placeholder="2026-11-08T13:30:05Z"
              required
            />
          </label>
          <button
            type="submit"
            className="w-fit rounded-md bg-jade px-4 py-2 text-sm font-semibold text-obsidian"
          >
            Add source event
          </button>
        </form>
        {eventNotice !== null ? (
          <p className="text-sm text-muted" role="alert">
            {eventNotice}
          </p>
        ) : null}
        {events.status === "loading" ? (
          <p className="text-sm text-muted">Loading source events.</p>
        ) : null}
        {events.status === "unavailable" ? (
          <p className="text-sm text-muted" role="alert">
            Source events are unavailable. No event was invented.
          </p>
        ) : null}
        {events.status === "ready" && events.events.length === 0 ? (
          <p className="text-sm text-muted">{EVENT_EMPTY}</p>
        ) : null}
        {events.status === "ready" && events.events.length > 0 ? (
          <ul className="grid max-w-xl gap-3">
            {events.events.map((item) => (
              <li key={item.id} className="rounded-md border border-line bg-panel p-4">
                <div className="flex items-start justify-between gap-3">
                  <h3 className="text-base font-semibold">{item.title}</h3>
                  <button
                    type="button"
                    className="rounded-md border border-line px-3 py-1 text-sm"
                    onClick={() => void removeEvent(item.id)}
                  >
                    Delete source event
                  </button>
                </div>
                <p className="mt-2 text-sm">Source {item.source}</p>
                <p className="mt-2 text-sm">Event time {item.event_time}</p>
                <p className="mt-2 text-sm">First public time {item.first_public_at}</p>
                <p className="mt-2 text-sm">{publicLagLine(item.event_time, item.first_public_at)}</p>
                <p className="text-sm text-warn">{PUBLIC_LAG_NOTE}</p>
                <p className="mt-2 text-xs text-muted">Recorded at {item.recorded_at}.</p>
                <p className="mt-2 text-sm">{recordAgeLine(item.recorded_at, now)}</p>
                <p className="text-sm text-warn">{RECORD_AGE_NOTE}</p>
              </li>
            ))}
          </ul>
        ) : null}
      </section>
    </div>
  );
}
