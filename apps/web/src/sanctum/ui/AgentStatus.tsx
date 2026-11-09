type TaskStatus = "complete" | "pending" | "running";

export type AgentStatusTask = {
  id: string;
  label: string;
  status: TaskStatus;
};

type AgentStatusProps = {
  title: string;
  detail?: string;
  tasks?: AgentStatusTask[];
};

function Mark({ status }: { status: TaskStatus }) {
  const label = status === "complete" ? "Complete" : status === "running" ? "Running" : "Pending";
  return (
    <span
      aria-label={label}
      className={`inline-block size-2 rounded-full ${status === "running" ? "bg-jade" : status === "complete" ? "bg-jade-2" : "bg-line"}`}
    />
  );
}

/** Adapted from 21st.dev Agent Status (demo 36497). Icons and the card shell were removed so this stays on the local Tailwind theme. */
export function AgentStatus({ title, detail, tasks = [] }: AgentStatusProps) {
  const complete = tasks.filter((task) => task.status === "complete").length;
  return (
    <section className="rounded-md border border-line bg-panel p-3 text-sm text-muted">
      <header className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <h3 className="truncate font-semibold text-ink">{title}</h3>
          {detail ? <p className="mt-0.5 text-xs leading-5">{detail}</p> : null}
        </div>
        {tasks.length > 0 ? (
          <span className="font-mono text-xs">
            {complete}/{tasks.length}
          </span>
        ) : null}
      </header>
      {tasks.length > 0 ? (
        <ul className="mt-3 flex flex-col gap-1 rounded-md bg-obsidian/60 p-2">
          {tasks.map((task) => (
            <li key={task.id} className="flex items-center gap-2 px-2 py-1 text-xs">
              <Mark status={task.status} />
              <span>{task.label}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
