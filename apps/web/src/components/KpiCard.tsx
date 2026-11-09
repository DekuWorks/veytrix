type KpiCardProps = {
  label: string;
  value: string;
  detail: string;
  activity?: string;
  activityCaption?: string;
  note?: string;
  extra?: string;
  caption?: string;
  position?: string;
  positionCaption?: string;
};

export function KpiCard({
  label,
  value,
  detail,
  activity,
  activityCaption,
  note,
  extra,
  caption,
  position,
  positionCaption,
}: KpiCardProps) {
  return (
    <article className="rounded-md border border-line bg-panel p-4">
      <h3 className="text-sm text-muted">{label}</h3>
      <p className="mt-2 font-mono text-2xl text-ink">{value}</p>
      <p className="mt-2 text-sm text-muted">{detail}</p>
      {activity !== undefined ? <p className="mt-2 text-sm text-muted">{activity}</p> : null}
      {activityCaption !== undefined ? <p className="mt-2 text-sm text-warn">{activityCaption}</p> : null}
      {note !== undefined ? <p className="mt-2 text-sm text-muted">{note}</p> : null}
      {extra !== undefined ? <p className="mt-2 text-sm text-muted">{extra}</p> : null}
      {caption !== undefined ? <p className="mt-2 text-sm text-warn">{caption}</p> : null}
      {position !== undefined ? <p className="mt-2 text-sm text-muted">{position}</p> : null}
      {positionCaption !== undefined ? <p className="mt-2 text-sm text-warn">{positionCaption}</p> : null}
    </article>
  );
}
