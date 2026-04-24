export function StatCard({
  label,
  value,
  accent,
}: {
  label: string;
  value: string | number;
  accent?: boolean;
}) {
  return (
    <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6">
      <div className="text-xs uppercase tracking-wider text-zinc-500">{label}</div>
      <div
        className={`mt-2 text-4xl font-bold tabular-nums ${
          accent ? "text-brand" : "text-white"
        }`}
      >
        {value}
      </div>
    </div>
  );
}
