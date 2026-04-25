import { headers } from "next/headers";
import { API_BASE, apiGet, type CheckResult } from "@/lib/api";
import { DeepAnalysis } from "@/components/DeepAnalysis";

type Stats = { total_blocked: number };

// Block page is rendered while the user's browser is on a SCAM domain
// (e.g. paypa1.com). Any relative href would stay on that scam host and
// just hit the block-page nginx vhost again. We need an absolute URL to
// the real ScamLens domain. Derive it from NEXT_PUBLIC_API_URL by
// stripping the trailing "/api".
const SITE_URL = API_BASE.replace(/\/api\/?$/, "") || "https://scamlens.vendly.my";

async function lookup(domain: string): Promise<CheckResult | null> {
  try {
    return await apiGet<CheckResult>(`/check/${encodeURIComponent(domain)}`);
  } catch {
    return null;
  }
}

async function getStats(): Promise<Stats | null> {
  try {
    return await apiGet<Stats>("/stats");
  } catch {
    return null;
  }
}

type Geo = {
  success: boolean;
  ip?: string;
  country?: string;
  country_code?: string;
  region?: string;
  city?: string;
  flag_emoji?: string;
  connection?: { asn?: number; org?: string; isp?: string };
  message?: string;
};

async function getGeo(ip: string): Promise<Geo | null> {
  try {
    return await apiGet<Geo>(`/geo/${ip}`);
  } catch {
    return null;
  }
}

export default async function BlockPage() {
  const h = await headers();
  const host = (h.get("x-original-host") || h.get("host") || "").split(":")[0];
  const [result, stats] = await Promise.all([
    host ? lookup(host) : Promise.resolve(null),
    getStats(),
  ]);

  const reason = result?.reason ?? "Known scam or phishing domain on our blocklist.";
  const brand = result?.mimics_brand ?? null;
  const risk = result?.risk_score ?? null;
  const source = result?.source ?? null;
  const resolvedIp = result?.resolved_ip ?? null;
  const geo = resolvedIp ? await getGeo(resolvedIp) : null;
  const placeParts = geo && geo.success
    ? [geo.city, geo.region, geo.country].filter(Boolean)
    : [];
  const place = placeParts.join(", ");
  const isp = geo?.connection?.isp || geo?.connection?.org || null;
  const asn = geo?.connection?.asn ? `AS${geo.connection.asn}` : null;

  return (
    <main className="mx-auto max-w-2xl px-6 py-10">
      <div className="rounded-3xl border border-red-500/40 bg-gradient-to-b from-red-950/40 to-zinc-950 p-8 shadow-2xl">
        <div className="flex items-start gap-4">
          <ShieldIcon />
          <div className="flex-1">
            <div className="text-xs font-semibold uppercase tracking-widest text-red-400">
              Access blocked
            </div>
            <h1 className="mt-1 text-2xl font-bold leading-tight">
              This page is dangerous
            </h1>
            <p className="mt-1 break-all font-mono text-sm text-zinc-400">
              {host || "(unknown)"}
            </p>
          </div>
        </div>

        <div className="mt-6 rounded-2xl border border-zinc-800 bg-black/40 p-5">
          <div className="text-xs uppercase tracking-wider text-zinc-500">
            Why we blocked it
          </div>
          <p className="mt-2 text-zinc-100">{reason}</p>

          {brand && (
            <div className="mt-4 rounded-lg border border-amber-500/30 bg-amber-950/20 p-3 text-sm">
              <div className="font-semibold text-amber-200">
                Impersonating {brand}
              </div>
              <div className="mt-0.5 text-amber-200/80">
                This domain looks like {brand} but is not owned by them.
              </div>
            </div>
          )}

          <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-2 text-xs text-zinc-400">
            {risk !== null && (
              <div>
                <span className="text-zinc-500">Risk score</span>{" "}
                <span className="font-semibold text-zinc-200">{risk}/100</span>
              </div>
            )}
            {source && (
              <div>
                <span className="text-zinc-500">Source</span>{" "}
                <span className="font-semibold text-zinc-200">
                  {labelSource(source)}
                </span>
              </div>
            )}
          </div>
        </div>

        {resolvedIp && (
          <div className="mt-4 rounded-2xl border border-zinc-800 bg-black/40 p-5 text-sm">
            <div className="text-xs uppercase tracking-wider text-zinc-500">
              Where this scam is hosted
            </div>
            <div className="mt-2 grid gap-1 text-zinc-200">
              <div>
                <span className="text-zinc-500">IP:</span>{" "}
                <span className="font-mono">{resolvedIp}</span>
              </div>
              {place && (
                <div>
                  <span className="text-zinc-500">Location:</span>{" "}
                  {geo?.flag_emoji ? `${geo.flag_emoji} ` : ""}
                  {place}
                </div>
              )}
              {(isp || asn) && (
                <div>
                  <span className="text-zinc-500">Hosted by:</span>{" "}
                  {isp ?? "—"}
                  {asn ? ` (${asn})` : ""}
                </div>
              )}
            </div>
          </div>
        )}

        <div className="mt-6 grid gap-3 sm:grid-cols-2">
          <a
            href={SITE_URL}
            className="flex items-center justify-center rounded-xl bg-brand px-5 py-3 font-semibold text-white hover:bg-brand-dark"
          >
            ← Take me back to safety
          </a>
          <a
            href={`${SITE_URL}/report?domain=${encodeURIComponent(host || "")}`}
            className="flex items-center justify-center rounded-xl border border-zinc-700 px-5 py-3 font-semibold text-zinc-200 hover:border-zinc-500"
          >
            Report false positive
          </a>
        </div>
      </div>

      {host && <DeepAnalysis domain={host} />}

      {stats && (
        <p className="mt-6 text-center text-sm text-zinc-500">
          ScamLens has blocked{" "}
          <span className="font-semibold text-zinc-300">
            {stats.total_blocked.toLocaleString()}
          </span>{" "}
          scam attempts on this network.
        </p>
      )}

      <div className="mt-10 rounded-2xl border border-zinc-800 bg-zinc-900/30 p-5 text-sm text-zinc-300">
        <div className="font-semibold">What to do next</div>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-zinc-400">
          <li>Don&apos;t enter any passwords, OTP codes, or card details on this page.</li>
          <li>If the link arrived in a message, delete the message.</li>
          <li>If you already entered credentials, change them now and enable 2FA.</li>
          <li>
            Is this a mistake? Hit{" "}
            <span className="text-zinc-200">Report false positive</span> — we
            review every submission.
          </li>
        </ul>
      </div>
    </main>
  );
}

function ShieldIcon() {
  return (
    <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-red-500/15 text-red-300 ring-1 ring-red-500/40">
      <svg viewBox="0 0 24 24" fill="none" className="h-8 w-8" aria-hidden>
        <path
          d="M12 2 4 5v6c0 5 3.5 9.5 8 11 4.5-1.5 8-6 8-11V5l-8-3Z"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinejoin="round"
        />
        <path
          d="m9 12 2 2 4-4"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </div>
  );
}

function labelSource(s: string): string {
  switch (s) {
    case "blocklist":
      return "Known scam database";
    case "typosquat":
      return "Brand-impersonation detector";
    case "ai":
      return "AI analysis";
    case "scan_error":
      return "Pending verification";
    default:
      return s;
  }
}
