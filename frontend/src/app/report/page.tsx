"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { apiPost } from "@/lib/api";

type ReportResult = { id: number; domain: string; status: string };

export default function ReportPage() {
  return (
    <Suspense fallback={<div className="mx-auto max-w-2xl px-6 py-16">Loading…</div>}>
      <ReportForm />
    </Suspense>
  );
}

function ReportForm() {
  const params = useSearchParams();
  const [domain, setDomain] = useState(params.get("domain") ?? "");
  const [note, setNote] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "done" | "error">("idle");
  const [result, setResult] = useState<ReportResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setState("sending");
    setError(null);
    try {
      const r = await apiPost<ReportResult>("/report", { domain, note: note || null });
      setResult(r);
      setState("done");
    } catch (err) {
      setError(err instanceof Error ? err.message : "submission failed");
      setState("error");
    }
  }

  return (
    <main className="mx-auto max-w-2xl px-6 py-16">
      <h1 className="text-3xl font-bold">Report a scam domain</h1>
      <p className="mt-2 text-zinc-400">
        Help protect others. We review submissions and add confirmed scams to the blocklist.
      </p>

      {state === "done" && result ? (
        <div className="mt-8 rounded-2xl border border-emerald-600/40 bg-emerald-950/30 p-6">
          <div className="font-semibold text-emerald-200">Thanks — report received.</div>
          <div className="mt-2 text-sm text-zinc-300">
            Domain: <span className="font-mono">{result.domain}</span>
          </div>
          <div className="text-sm text-zinc-300">Status: {result.status}</div>
          <button
            onClick={() => {
              setState("idle");
              setDomain("");
              setNote("");
              setResult(null);
            }}
            className="mt-4 rounded-lg border border-zinc-700 px-4 py-2 text-sm hover:border-zinc-500"
          >
            Submit another
          </button>
        </div>
      ) : (
        <form onSubmit={onSubmit} className="mt-8 space-y-4">
          <label className="block">
            <span className="text-sm text-zinc-300">Domain or URL</span>
            <input
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              required
              placeholder="fake-bank-login.xyz"
              className="mt-1 w-full rounded-xl border border-zinc-700 bg-zinc-900 px-4 py-3 outline-none focus:border-brand"
            />
          </label>
          <label className="block">
            <span className="text-sm text-zinc-300">Notes (optional)</span>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={4}
              placeholder="Where did you see this? What did it claim to be?"
              className="mt-1 w-full rounded-xl border border-zinc-700 bg-zinc-900 px-4 py-3 outline-none focus:border-brand"
            />
          </label>
          <button
            disabled={state === "sending"}
            className="rounded-xl bg-brand px-6 py-3 font-semibold hover:bg-brand-dark disabled:opacity-60"
          >
            {state === "sending" ? "Submitting…" : "Submit report"}
          </button>
          {error && <p className="text-sm text-red-400">{error}</p>}
        </form>
      )}
    </main>
  );
}
