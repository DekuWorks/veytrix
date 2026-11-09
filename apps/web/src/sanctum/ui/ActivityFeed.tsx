export type ActivityLine = {
  id: string;
  message: string;
  time: string;
};

type ActivityFeedProps = {
  title: string;
  lines: ActivityLine[];
};

/** Adapted from 21st.dev Dashboard Activities (demo 8372). Motion and icon libraries are not in this app, so each row is a static line. */
export function ActivityFeed({ title, lines }: ActivityFeedProps) {
  return (
    <section className="text-sm">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-jade-2">{title}</h2>
      {lines.length === 0 ? (
        <p className="mt-2 text-xs text-muted">No recent activity to display.</p>
      ) : (
        <ul className="mt-2 divide-y divide-line">
          {lines.map((line) => (
            <li key={line.id} className="py-2">
              <p className="text-xs leading-5 text-ink">{line.message}</p>
              <p className="text-[11px] text-muted">{line.time}</p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
