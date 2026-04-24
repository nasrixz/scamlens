"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  AdminAuthError,
  adminApi,
  type AdminReport,
  type DomainRow,
} from "@/lib/admin";

type Tab = "reports" | "blocklist" | "whitelist";

export default function AdminHome() {
  const router = useRouter();
  const [me, setMe] = useState<{ email: string; role: string } | null>(null);
  const [counts, setCounts] = useState<{
    pending_reports: number;
    blocklist: number;
    whitelist: number;
    brands: number;
  } | null>(null);
  const [tab, setTab] = useState<Tab>("reports");

  useEffect(() => {
    adminApi
      .me()
      .then(setMe)
      .catch((e) => {
        if (e instanceof AdminAuthError) router.replace("/admin/login");
      });
    adminApi.counts().then(setCounts).catch(() => undefined);
  }, [router]);

  if (!me) {
    return <div className="p-6 text-zinc-400">Loading…</div>;
  }

  return (
    <main className="mx-auto max-w-6xl px-6 py-8">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Admin</h1>
          <p className="text-sm text-zinc-400">Signed in as {me.email}</p>
        </div>
        <button
          onClick={async () => {
            await adminApi.logout().catch(() => undefined);
            router.replace("/admin/login");
          }}
          className="rounded-lg border border-zinc-700 px-3 py-1.5 text-sm hover:border-zinc-500"
        >
          Sign out
        </button>
      </header>

      {counts && (
        <section className="mt-6 grid gap-3 sm:grid-cols-4">
          <Stat label="Pending reports" value={counts.pending_reports} />
          <Stat label="Blocklist" value={counts.blocklist} />
          <Stat label="Whitelist" value={counts.whitelist} />
          <Stat label="Brand anchors" value={counts.brands} />
        </section>
      )}

      <nav className="mt-8 flex gap-2">
        {(["reports", "blocklist", "whitelist"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`rounded-full px-4 py-1.5 text-sm ${
              tab === t
                ? "bg-brand text-white"
                : "border border-zinc-700 text-zinc-300 hover:border-zinc-500"
            }`}
          >
            {t[0].toUpperCase() + t.slice(1)}
          </button>
        ))}
      </nav>

      <div className="mt-6">
        {tab === "reports" && <ReportsPanel onChange={() => reloadCounts(setCounts)} />}
        {tab === "blocklist" && <DomainPanel kind="blocklist" onChange={() => reloadCounts(setCounts)} />}
        {tab === "whitelist" && <DomainPanel kind="whitelist" onChange={() => reloadCounts(setCounts)} />}
      </div>
    </main>
  );
}

function reloadCounts(setter: (c: any) => void) {
  adminApi.counts().then(setter).catch(() => undefined);
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
      <div className="text-xs uppercase text-zinc-500">{label}</div>
      <div className="mt-1 text-2xl font-bold tabular-nums">{value}</div>
    </div>
  );
}

// -------------------------------- reports -----------------------------------

function ReportsPanel({ onChange }: { onChange: () => void }) {
  const [filter, setFilter] = useState<"pending" | "confirmed" | "rejected" | "all">("pending");
  const [items, setItems] = useState<AdminReport[]>([]);
  const [busy, setBusy] = useState<number | null>(null);

  async function load() {
    const r = await adminApi.listReports(filter);
    setItems(r.items);
  }
  useEffect(() => {
    load();
  }, [filter]);

  async function act(id: number, fn: () => Promise<unknown>) {
    setBusy(id);
    try {
      await fn();
      await load();
      onChange();
    } finally {
      setBusy(null);
    }
  }

  return (
    <div>
      <div className="mb-3 flex items-center gap-2 text-sm">
        {(["pending", "confirmed", "rejected", "all"] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`rounded-lg border px-3 py-1 ${
              filter === f ? "border-brand text-brand" : "border-zinc-700 text-zinc-300"
            }`}
          >
            {f}
          </button>
        ))}
      </div>
      <div className="overflow-hidden rounded-xl border border-zinc-800">
        <table className="w-full text-left text-sm">
          <thead className="bg-zinc-900/60 text-xs uppercase text-zinc-500">
            <tr>
              <th className="px-4 py-2">When</th>
              <th className="px-4 py-2">Domain</th>
              <th className="px-4 py-2">Note</th>
              <th className="px-4 py-2">Status</th>
              <th className="px-4 py-2 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800">
            {items.map((r) => (
              <tr key={r.id}>
                <td className="px-4 py-2 text-zinc-400">
                  {new Date(r.created_at).toLocaleString()}
                </td>
                <td className="px-4 py-2 font-medium">{r.domain}</td>
                <td className="px-4 py-2 text-zinc-400">{r.note ?? "—"}</td>
                <td className="px-4 py-2">{r.status}</td>
                <td className="px-4 py-2 text-right">
                  {r.status === "pending" && (
                    <div className="flex justify-end gap-2">
                      <button
                        disabled={busy === r.id}
                        onClick={() => act(r.id, () => adminApi.confirmReport(r.id))}
                        className="rounded-lg bg-brand px-3 py-1 text-xs font-semibold text-white hover:bg-brand-dark disabled:opacity-60"
                      >
                        Confirm → block
                      </button>
                      <button
                        disabled={busy === r.id}
                        onClick={() => act(r.id, () => adminApi.rejectReport(r.id))}
                        className="rounded-lg border border-zinc-700 px-3 py-1 text-xs hover:border-zinc-500 disabled:opacity-60"
                      >
                        Reject
                      </button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
            {items.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-zinc-500">
                  No reports.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ----------------------- blocklist / whitelist panel ------------------------

function DomainPanel({
  kind,
  onChange,
}: {
  kind: "blocklist" | "whitelist";
  onChange: () => void;
}) {
  const [items, setItems] = useState<DomainRow[]>([]);
  const [domain, setDomain] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [filter, setFilter] = useState("");

  const listFn = kind === "blocklist" ? adminApi.listBlocklist : adminApi.listWhitelist;
  const addFn = kind === "blocklist" ? adminApi.addBlocklist : adminApi.addWhitelist;
  const removeFn = kind === "blocklist" ? adminApi.removeBlocklist : adminApi.removeWhitelist;

  async function load() {
    const r = await listFn();
    setItems(r.items);
  }
  useEffect(() => {
    load();
  }, [kind]);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await addFn(domain.trim(), reason.trim() || undefined);
      setDomain("");
      setReason("");
      await load();
      onChange();
    } finally {
      setBusy(false);
    }
  }

  async function remove(d: string) {
    if (!confirm(`Remove ${d} from ${kind}?`)) return;
    await removeFn(d);
    await load();
    onChange();
  }

  const visible = items.filter((r) => r.domain.includes(filter));

  return (
    <div>
      <form onSubmit={add} className="mb-4 flex flex-wrap gap-2">
        <input
          value={domain}
          onChange={(e) => setDomain(e.target.value)}
          placeholder="domain.com"
          required
          className="flex-1 min-w-[200px] rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm outline-none focus:border-brand"
        />
        <input
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder={kind === "blocklist" ? "category (optional)" : "reason (optional)"}
          className="flex-1 min-w-[200px] rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm outline-none focus:border-brand"
        />
        <button
          disabled={busy}
          className="rounded-lg bg-brand px-4 py-2 text-sm font-semibold hover:bg-brand-dark disabled:opacity-60"
        >
          Add to {kind}
        </button>
      </form>

      <input
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        placeholder="Filter…"
        className="mb-3 w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm outline-none focus:border-brand sm:w-64"
      />

      <div className="overflow-hidden rounded-xl border border-zinc-800">
        <table className="w-full text-left text-sm">
          <thead className="bg-zinc-900/60 text-xs uppercase text-zinc-500">
            <tr>
              <th className="px-4 py-2">Domain</th>
              <th className="px-4 py-2">{kind === "blocklist" ? "Category" : "Reason"}</th>
              <th className="px-4 py-2">Added</th>
              <th className="px-4 py-2 text-right"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800">
            {visible.map((r) => (
              <tr key={r.domain}>
                <td className="px-4 py-2 font-medium">{r.domain}</td>
                <td className="px-4 py-2 text-zinc-400">
                  {r.category ?? r.reason ?? "—"}
                </td>
                <td className="px-4 py-2 text-zinc-400">
                  {new Date(r.added_at).toLocaleString()}
                </td>
                <td className="px-4 py-2 text-right">
                  <button
                    onClick={() => remove(r.domain)}
                    className="rounded-lg border border-zinc-700 px-3 py-1 text-xs hover:border-red-500 hover:text-red-300"
                  >
                    Remove
                  </button>
                </td>
              </tr>
            ))}
            {visible.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-zinc-500">
                  Nothing here.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
