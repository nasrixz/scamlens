"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  AdminAuthError,
  adminApi,
  type AdminReport,
  type DomainRow,
  type ScanReport,
} from "@/lib/admin";

type Tab = "reports" | "blocklist" | "whitelist" | "scan";

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

      <nav className="mt-8 flex flex-wrap gap-2">
        {(["reports", "blocklist", "whitelist", "scan"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`rounded-full px-4 py-1.5 text-sm ${
              tab === t
                ? "bg-brand text-white"
                : "border border-zinc-700 text-zinc-300 hover:border-zinc-500"
            }`}
          >
            {t === "scan" ? "Test scan" : t[0].toUpperCase() + t.slice(1)}
          </button>
        ))}
      </nav>

      <div className="mt-6">
        {tab === "reports" && <ReportsPanel onChange={() => reloadCounts(setCounts)} />}
        {tab === "blocklist" && <DomainPanel kind="blocklist" onChange={() => reloadCounts(setCounts)} />}
        {tab === "whitelist" && <DomainPanel kind="whitelist" onChange={() => reloadCounts(setCounts)} />}
        {tab === "scan" && <ScanPanel />}
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
                  <div>{r.category ?? r.reason ?? "—"}</div>
                  {r.source_post && (
                    <a
                      href={r.source_post}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-brand hover:underline"
                    >
                      ↗ source post ({r.source_platform ?? "link"})
                    </a>
                  )}
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

// -------------------------------- test scan ---------------------------------

function ScanPanel() {
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [report, setReport] = useState<ScanReport | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function run(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    setReport(null);
    try {
      const r = await adminApi.scan(url.trim());
      setReport(r);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "scan failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <form onSubmit={run} className="flex flex-wrap gap-2">
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://example.com or any-domain.xyz"
          required
          className="flex-1 min-w-[280px] rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm outline-none focus:border-brand"
        />
        <button
          disabled={busy || !url.trim()}
          className="rounded-lg bg-brand px-4 py-2 text-sm font-semibold hover:bg-brand-dark disabled:opacity-60"
        >
          {busy ? "Scanning… (up to 60s)" : "Scan with AI"}
        </button>
      </form>
      {err && <div className="text-sm text-red-400">{err}</div>}

      {report && <ScanReportView report={report} />}
    </div>
  );
}

function ScanReportView({ report }: { report: ScanReport }) {
  if (!report.fetched) {
    return (
      <div className="rounded-xl border border-amber-500/40 bg-amber-950/20 p-4 text-sm text-amber-200">
        <div className="font-semibold">Couldn&apos;t fetch {report.domain}</div>
        <div className="mt-1 text-amber-200/80">{report.error}</div>
      </div>
    );
  }
  if (report.empty_page) {
    return (
      <div className="rounded-xl border border-zinc-700 bg-zinc-900/40 p-4 text-sm">
        <div className="font-semibold text-zinc-200">
          Skipped AI — {report.empty_reason ?? "page is empty"}
        </div>
        <div className="mt-1 text-zinc-400">
          Page returned no content for the AI to analyze. Saved one scan call.
        </div>
        {report.screenshot_base64 && (
          <img
            src={`data:image/png;base64,${report.screenshot_base64}`}
            alt="Empty page"
            className="mt-3 rounded-lg w-full"
          />
        )}
      </div>
    );
  }

  const v = report.verdict;
  const vColor =
    v?.verdict === "scam"
      ? "border-red-500/50 bg-red-950/30 text-red-200"
      : v?.verdict === "suspicious"
      ? "border-amber-500/40 bg-amber-950/20 text-amber-200"
      : "border-emerald-500/40 bg-emerald-950/20 text-emerald-200";

  return (
    <div className="space-y-5">
      <div className={`rounded-2xl border p-5 ${vColor}`}>
        <div className="flex items-baseline justify-between">
          <div>
            <div className="text-xs uppercase tracking-widest opacity-80">AI verdict</div>
            <div className="mt-1 text-2xl font-bold">{v?.verdict ?? "—"}</div>
          </div>
          <div className="text-right text-xs opacity-80">
            <div>Risk {v?.risk_score ?? "—"}/100</div>
            <div>Confidence {v?.confidence ?? "—"}%</div>
            <div>Model {v?.model ?? "—"}</div>
          </div>
        </div>
        {v?.mimics_brand && (
          <div className="mt-3 text-sm">
            Impersonating: <strong>{v.mimics_brand}</strong>
          </div>
        )}
        {v?.reasons?.length ? (
          <ul className="mt-3 list-disc space-y-1 pl-5 text-sm">
            {v.reasons.map((r, i) => (<li key={i}>{r}</li>))}
          </ul>
        ) : null}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4 text-sm">
          <div className="text-xs uppercase text-zinc-500">Page metadata</div>
          <dl className="mt-2 space-y-1">
            <Field label="Domain" value={report.domain} mono />
            <Field label="Final URL" value={report.final_url} mono />
            <Field label="HTTP status" value={report.status?.toString()} />
            <Field label="Title" value={report.title} />
            <Field
              label="Domain age"
              value={
                report.domain_age_days != null
                  ? `${report.domain_age_days} days`
                  : "unknown (RDAP)"
              }
            />
          </dl>
        </div>
        {report.screenshot_base64 && (
          <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-2">
            <img
              src={`data:image/png;base64,${report.screenshot_base64}`}
              alt={`Screenshot of ${report.domain}`}
              className="rounded-lg w-full"
            />
          </div>
        )}
      </div>

      {report.links && report.links.length > 0 && (
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
          <div className="text-xs uppercase text-zinc-500">
            External domains found ({report.links.length})
          </div>
          <table className="mt-3 w-full text-left text-sm">
            <thead className="text-xs uppercase text-zinc-500">
              <tr>
                <th className="px-2 py-1">Domain</th>
                <th className="px-2 py-1">Cached verdict</th>
                <th className="px-2 py-1">First seen</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800">
              {report.links.map((l) => (
                <tr key={l.domain}>
                  <td className="px-2 py-1 font-mono">{l.domain}</td>
                  <td className="px-2 py-1">
                    {l.cached_verdict ? (
                      <span
                        className={
                          l.cached_verdict.verdict === "scam"
                            ? "text-red-400"
                            : l.cached_verdict.verdict === "suspicious"
                            ? "text-amber-300"
                            : "text-emerald-300"
                        }
                      >
                        {l.cached_verdict.verdict} ({l.cached_verdict.source ?? "cache"})
                      </span>
                    ) : (
                      <span className="text-zinc-500">unscanned</span>
                    )}
                  </td>
                  <td className="px-2 py-1 truncate max-w-[280px] text-zinc-500">
                    {l.first_seen_href}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {report.html_excerpt && (
        <details className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
          <summary className="cursor-pointer text-xs uppercase text-zinc-500">
            HTML excerpt (first 8 KB)
          </summary>
          <pre className="mt-2 overflow-x-auto rounded bg-black/40 p-3 text-xs leading-snug">
            {report.html_excerpt}
          </pre>
        </details>
      )}
    </div>
  );
}

function Field({ label, value, mono }: { label: string; value?: string; mono?: boolean }) {
  return (
    <div className="flex gap-2">
      <dt className="w-28 shrink-0 text-zinc-500">{label}</dt>
      <dd className={mono ? "font-mono break-all" : "break-words"}>{value ?? "—"}</dd>
    </div>
  );
}
