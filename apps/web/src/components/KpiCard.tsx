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
    <article className="vx-card">
      <h3 className="text-sm text-muted">{label}</h3>
      <p className="mt-3 font-mono text-[clamp(1.5rem,3vw,1.75rem)] leading-none tracking-tight text-jade-2">{value}</p>
      <p className="vx-copy">{detail}</p>
      {activity !== undefined ? <p className="vx-copy">{activity}</p> : null}
      {note !== undefined ? <p className="vx-copy">{note}</p> : null}
      {extra !== undefined ? <p className="vx-copy">{extra}</p> : null}
      {position !== undefined ? <p className="vx-copy">{position}</p> : null}
    </article>
  );
}
