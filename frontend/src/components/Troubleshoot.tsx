import { ReactNode } from "react";

export function Troubleshoot({ items }: { items: { q: string; a: ReactNode }[] }) {
  return (
    <details className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-5">
      <summary className="cursor-pointer text-sm font-semibold text-zinc-200">
        Troubleshooting
      </summary>
      <div className="mt-4 space-y-4 text-sm text-zinc-300">
        {items.map((t, i) => (
          <div key={i}>
            <div className="font-medium text-zinc-100">{t.q}</div>
            <div className="mt-1 text-zinc-400">{t.a}</div>
          </div>
        ))}
      </div>
    </details>
  );
}
