import Link from "next/link";
import { headers } from "next/headers";
import { apiGet, type CheckResult } from "@/lib/api";

async function lookup(domain: string): Promise<CheckResult | null> {
  try {
    return await apiGet<CheckResult>(`/check/${encodeURIComponent(domain)}`);
  } catch {
    return null;
  }
}

export default async function BlockPage() {
  const h = await headers();
  const host = (h.get("x-original-host") || h.get("host") || "").split(":")[0];
  const result = host ? await lookup(host) : null;

  return (
    <main className="mx-auto max-w-2xl px-6 py-16">
      <div className="rounded-3xl border-2 border-brand bg-red-950/30 p-10 text-center">
        <div className="text-6xl">🚫</div>
        <h1 className="mt-4 text-3xl font-bold">ScamLens blocked this site</h1>
        <p className="mt-2 text-lg text-zinc-300">
          <span className="font-mono text-white">{host || "(unknown)"}</span>
        </p>

        <div className="mt-8 rounded-xl bg-black/30 p-5 text-left">
          <div className="text-xs uppercase tracking-wider text-zinc-400">Why we blocked this</div>
          <p className="mt-2 text-zinc-100">
            {result?.reason ?? "Known scam or phishing domain on our blocklist."}
          </p>
          {result?.mimics_brand && (
            <p className="mt-2 text-sm text-zinc-300">
              Appears to impersonate: <strong>{result.mimics_brand}</strong>
            </p>
          )}
          {typeof result?.risk_score === "number" && (
            <p className="mt-2 text-sm text-zinc-400">
              Risk score: {result.risk_score}/100 · confidence {result.confidence ?? "—"}%
            </p>
          )}
        </div>

        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Link
            href="https://www.google.com"
            className="rounded-xl bg-brand px-6 py-3 font-semibold hover:bg-brand-dark"
          >
            Go back to safety
          </Link>
          <Link
            href={`/report?domain=${encodeURIComponent(host || "")}`}
            className="rounded-xl border border-zinc-600 px-6 py-3 font-semibold text-zinc-200 hover:border-zinc-400"
          >
            Report false positive
          </Link>
        </div>
      </div>
    </main>
  );
}
