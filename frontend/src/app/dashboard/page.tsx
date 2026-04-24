"use client";

import { Fragment, useState } from "react";
import useSWR from "swr";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fetcher, type BlockedPage, type Stats } from "@/lib/api";
import { StatCard } from "@/components/StatCard";

export default function Dashboard() {
  const { data: stats } = useSWR<Stats>("/stats", fetcher, { refreshInterval: 10000 });
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const { data: blocked } = useSWR<BlockedPage>(
    `/blocked?page=${page}&page_size=25${q ? `&q=${encodeURIComponent(q)}` : ""}`,
    fetcher,
    { refreshInterval: 10000 },
  );
  const [expanded, setExpanded] = useState<number | null>(null);

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <h1 className="text-3xl font-bold">Dashboard</h1>
      <p className="mt-2 text-sm text-zinc-400">Auto-refreshes every 10 seconds.</p>

      <section className="mt-8 grid gap-4 sm:grid-cols-3">
        <StatCard label="Blocked today" value={fmt(stats?.blocked_today)} accent />
        <StatCard label="Total blocked" value={fmt(stats?.total_blocked)} />
        <StatCard label="Unique domains" value={fmt(stats?.unique_domains)} />
      </section>

      <section className="mt-8 grid gap-4 lg:grid-cols-3">
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-5 lg:col-span-2">
          <div className="text-sm font-semibold text-zinc-300">Blocks per day · last 7d</div>
          <div className="mt-4 h-56">
            <ResponsiveContainer>
              <BarChart data={stats?.daily ?? []}>
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                <XAxis dataKey="day" tick={{ fill: "#71717a", fontSize: 11 }} />
                <YAxis tick={{ fill: "#71717a", fontSize: 11 }} />
                <Tooltip
                  cursor={{ fill: "#27272a" }}
                  contentStyle={{
                    background: "#18181b",
                    border: "1px solid #3f3f46",
                    borderRadius: 8,
                  }}
                />
                <Bar dataKey="count" fill="#ef4444" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-5">
          <div className="text-sm font-semibold text-zinc-300">Top offenders · 7d</div>
          <ul className="mt-3 space-y-2 text-sm">
            {(stats?.top_domains ?? []).map((d) => (
              <li key={d.domain} className="flex items-center justify-between">
                <span className="truncate text-zinc-200">{d.domain}</span>
                <span className="tabular-nums text-zinc-500">{d.count}</span>
              </li>
            ))}
            {(stats?.top_domains ?? []).length === 0 && (
              <li className="text-zinc-500">No data yet.</li>
            )}
          </ul>
        </div>
      </section>

      <section className="mt-10">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Recent blocks</h2>
          <input
            value={q}
            onChange={(e) => {
              setPage(1);
              setQ(e.target.value);
            }}
            placeholder="Filter domain…"
            className="w-64 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-sm outline-none focus:border-brand"
          />
        </div>

        <div className="mt-4 overflow-hidden rounded-2xl border border-zinc-800">
          <table className="w-full text-left text-sm">
            <thead className="bg-zinc-900/60 text-xs uppercase tracking-wider text-zinc-500">
              <tr>
                <th className="px-4 py-3">When</th>
                <th className="px-4 py-3">Domain</th>
                <th className="px-4 py-3">Reason</th>
                <th className="px-4 py-3 text-right">Confidence</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800">
              {(blocked?.items ?? []).map((row) => (
                <Fragment key={row.id}>
                  <tr
                    className="cursor-pointer hover:bg-zinc-900/40"
                    onClick={() => setExpanded(expanded === row.id ? null : row.id)}
                  >
                    <td className="px-4 py-3 text-zinc-400">
                      {new Date(row.created_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-3 font-medium">{row.domain}</td>
                    <td className="px-4 py-3 text-zinc-400">{row.reason}</td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {row.ai_confidence ?? "—"}
                    </td>
                  </tr>
                  {expanded === row.id && (
                    <tr className="bg-zinc-900/30">
                      <td colSpan={4} className="px-4 py-3 text-xs text-zinc-300">
                        <div>Verdict: {row.verdict ?? "—"}</div>
                        <div>Risk score: {row.risk_score ?? "—"}</div>
                        <div>Mimics brand: {row.mimics_brand ?? "—"}</div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
              {(blocked?.items ?? []).length === 0 && (
                <tr>
                  <td colSpan={4} className="px-4 py-6 text-center text-zinc-500">
                    No blocks yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {blocked && blocked.total > blocked.page_size && (
          <div className="mt-4 flex items-center justify-between text-sm text-zinc-400">
            <span>
              Page {blocked.page} of {Math.ceil(blocked.total / blocked.page_size)}
            </span>
            <div className="flex gap-2">
              <button
                disabled={page === 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="rounded-lg border border-zinc-700 px-3 py-1 disabled:opacity-40"
              >
                Prev
              </button>
              <button
                disabled={page * blocked.page_size >= blocked.total}
                onClick={() => setPage((p) => p + 1)}
                className="rounded-lg border border-zinc-700 px-3 py-1 disabled:opacity-40"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </section>
    </main>
  );
}

function fmt(n?: number) {
  return (n ?? 0).toLocaleString();
}
