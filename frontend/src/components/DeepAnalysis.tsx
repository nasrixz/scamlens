"use client";

import { useEffect, useState } from "react";
import { API_BASE } from "@/lib/api";

type DeepReport = {
  domain: string;
  fetched: boolean;
  error?: string;
  final_url?: string;
  status?: number;
  title?: string;
  screenshot_base64?: string;
  verdict?: {
    verdict: "safe" | "suspicious" | "scam";
    risk_score: number;
    confidence: number;
    reasons: string[];
    mimics_brand: string | null;
    model: string;
  };
  domain_age_days?: number | null;
  links?: {
    domain: string;
    cached_verdict: { verdict?: string; source?: string } | null;
  }[];
};

type Envelope =
  | { status: "idle" | "pending"; domain: string }
  | { status: "done"; domain: string; report: DeepReport };

export function DeepAnalysis({ domain }: { domain: string }) {
  const [state, setState] = useState<Envelope>({ status: "idle", domain });
  const [secs, setSecs] = useState(0);

  useEffect(() => {
    let cancelled = false;
    let pollTimer: ReturnType<typeof setTimeout> | null = null;
    let counterTimer: ReturnType<typeof setInterval> | null = null;

    async function kickoff() {
      try {
        const r = await fetch(`${API_BASE}/deep/${encodeURIComponent(domain)}`, {
          method: "POST",
        });
        if (!r.ok) throw new Error(`POST ${r.status}`);
        const j = (await r.json()) as Envelope;
        if (!cancelled) setState(j);
        if (!cancelled && j.status === "pending") schedule();
      } catch {
        // network / rate-limit — fall through to polling GET anyway
        if (!cancelled) schedule();
      }
    }

    async function poll() {
      try {
        const r = await fetch(`${API_BASE}/deep/${encodeURIComponent(domain)}`);
        const j = (await r.json()) as Envelope;
        if (cancelled) return;
        setState(j);
        if (j.status !== "done") schedule();
      } catch {
        if (!cancelled) schedule();
      }
    }

    function schedule() {
      pollTimer = setTimeout(poll, 4000);
    }

    counterTimer = setInterval(() => setSecs((s) => s + 1), 1000);
    kickoff();

    return () => {
      cancelled = true;
      if (pollTimer) clearTimeout(pollTimer);
      if (counterTimer) clearInterval(counterTimer);
    };
  }, [domain]);

  if (state.status !== "done") {
    return (
      <div className="mt-6 rounded-2xl border border-zinc-800 bg-zinc-900/40 p-5 text-sm">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-xs uppercase tracking-wider text-zinc-500">
              Deep web analysis
            </div>
            <div className="mt-1 font-semibold text-zinc-200">
              Loading the page in a sandbox and asking the AI to analyze it…
            </div>
            <div className="mt-1 text-xs text-zinc-500">
              This usually takes 20–60 seconds.
            </div>
          </div>
          <div className="flex items-center gap-2 text-zinc-400">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-500"></span>
            </span>
            <span className="tabular-nums text-xs">{secs}s</span>
          </div>
        </div>
      </div>
    );
  }

  const r = state.report;
  if (!r.fetched) {
    return (
      <div className="mt-6 rounded-2xl border border-zinc-800 bg-zinc-900/40 p-5 text-sm">
        <div className="text-xs uppercase tracking-wider text-zinc-500">
          Deep web analysis
        </div>
        <div className="mt-2 text-zinc-300">
          Couldn&apos;t load the page in a sandbox: {r.error ?? "fetch failed"}.
        </div>
      </div>
    );
  }

  const v = r.verdict;
  const tone =
    v?.verdict === "scam"
      ? "border-red-500/50 bg-red-950/20 text-red-200"
      : v?.verdict === "suspicious"
      ? "border-amber-500/40 bg-amber-950/20 text-amber-200"
      : "border-emerald-500/40 bg-emerald-950/20 text-emerald-200";

  return (
    <div className="mt-6 space-y-4">
      <div className={`rounded-2xl border p-5 ${tone}`}>
        <div className="flex items-baseline justify-between">
          <div>
            <div className="text-xs uppercase tracking-widest opacity-80">
              Deep web analysis (AI)
            </div>
            <div className="mt-1 text-xl font-bold">
              {v?.verdict ?? "—"}
            </div>
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
            {v.reasons.map((reason, i) => (
              <li key={i}>{reason}</li>
            ))}
          </ul>
        ) : null}
      </div>

      {r.screenshot_base64 && (
        <details className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4">
          <summary className="cursor-pointer text-xs uppercase text-zinc-500">
            Screenshot the AI saw
          </summary>
          <img
            src={`data:image/png;base64,${r.screenshot_base64}`}
            alt={`Screenshot of ${r.domain}`}
            className="mt-3 rounded-lg w-full"
          />
        </details>
      )}

      {r.links && r.links.length > 0 && (
        <details className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4">
          <summary className="cursor-pointer text-xs uppercase text-zinc-500">
            Outbound domains on the page ({r.links.length})
          </summary>
          <ul className="mt-3 space-y-1 text-sm">
            {r.links.slice(0, 30).map((l) => (
              <li key={l.domain} className="flex items-center justify-between gap-3">
                <span className="font-mono text-zinc-300 truncate">{l.domain}</span>
                <span className="text-xs text-zinc-500">
                  {l.cached_verdict?.verdict ?? "unscanned"}
                </span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
