import { useMemo, useState } from "react";

export type SanctumLog = {
  id: string;
  time: string;
  level: "info" | "error";
  service: string;
  message: string;
};

/** Adapted from 21st.dev Interactive Logs Table (demo 10635). Search and level filters stay; the sample payment rows do not. */
export function LogPanel({ logs }: { logs: SanctumLog[] }) {
  const [query, setQuery] = useState("");
  const [level, setLevel] = useState<"all" | "info" | "error">("all");
  const [openId, setOpenId] = useState<string | null>(null);

  const shown = useMemo(
    () =>
      logs.filter((log) => {
        const text = `${log.service} ${log.message}`.toLowerCase();
        const matchesQuery = text.includes(query.trim().toLowerCase());
        const matchesLevel = level === "all" || log.level === level;
        return matchesQuery && matchesLevel;
      }),
    [level, logs, query],
  );

  return (
    <section aria-label="Logs" className="flex h-full min-h-0 flex-col">
      <div className="flex gap-2">
        <input
          aria-label="Search logs"
          className="h-8 flex-1 rounded-md border border-line bg-obsidian px-2 text-sm text-ink"
          placeholder="Search logs"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        {(["all", "info", "error"] as const).map((item) => (
          <button
            key={item}
            type="button"
            aria-pressed={level === item}
            className="vx-btn capitalize"
            onClick={() => setLevel(item)}
          >
            {item}
          </button>
        ))}
      </div>
      <p className="mt-2 text-xs text-muted">
        {shown.length} of {logs.length} logs
      </p>
      <ul className="mt-2 min-h-0 flex-1 divide-y divide-line overflow-auto">
        {shown.length === 0 ? (
          <li className="py-6 text-sm text-muted">No logs match your filters.</li>
        ) : (
          shown.map((log) => (
            <li key={log.id}>
              <button type="button" className="flex w-full gap-3 py-2 text-left text-xs" onClick={() => setOpenId(openId === log.id ? null : log.id)}>
                <span className={log.level === "error" ? "text-danger" : "text-jade-2"}>{log.level}</span>
                <time className="font-mono text-muted">{log.time}</time>
                <span className="font-medium text-ink">{log.service}</span>
                <span className="truncate text-muted">{log.message}</span>
              </button>
              {openId === log.id ? <p className="mb-2 font-mono text-xs text-ink">{log.message}</p> : null}
            </li>
          ))
        )}
      </ul>
    </section>
  );
}
