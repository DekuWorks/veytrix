type KpiCardProps = {
  label: string;
  value: string;
  detail: string;
  activity?: string;
  note?: string;
  extra?: string;
  position?: string;
};

export function KpiCard({ label, value, detail, activity, note, extra, position }: KpiCardProps) {
  return (
    <article className="rounded-md border border-line bg-panel p-4">
      <h3 className="text-sm text-muted">{label}</h3>
      <p className="mt-2 font-mono text-2xl text-ink">{value}</p>
      <p className="mt-2 text-sm text-muted">{detail}</p>
      {activity !== undefined ? <p className="mt-2 text-sm text-muted">{activity}</p> : null}
      {note !== undefined ? <p className="mt-2 text-sm text-muted">{note}</p> : null}
      {extra !== undefined ? <p className="mt-2 text-sm text-muted">{extra}</p> : null}
      {position !== undefined ? <p className="mt-2 text-sm text-muted">{position}</p> : null}
    </article>
  );
}
