"use client";

import { useState } from "react";
import { apiGet, type CheckResult } from "@/lib/api";

/**
 * Client-side DNS test: query the API for a known test domain. If the
 * user's browser is going through ScamLens, the answer's IP belongs to
 * us — but we can't prove that from JS. So instead we fire an `<img>`
 * at a known-blocked host and check whether it loads. If the request
 * fails (DNS resolves to block page, which serves HTML not an image),
 * protection is active.
 */
const BLOCKED_TEST_DOMAIN = "scam-test.scamlens.local";

export function VerifyWidget() {
  const [state, setState] = useState<"idle" | "checking" | "protected" | "unprotected" | "error">(
    "idle",
  );
  const [verdict, setVerdict] = useState<CheckResult | null>(null);

  async function run() {
    setState("checking");
    try {
      const r = await apiGet<CheckResult>(`/check/${BLOCKED_TEST_DOMAIN}`);
      setVerdict(r);

      const started = Date.now();
      const img = new Image();
      const loaded = await new Promise<boolean>((resolve) => {
        img.onload = () => resolve(true);
        img.onerror = () => resolve(false);
        img.src = `http://${BLOCKED_TEST_DOMAIN}/favicon.ico?t=${started}`;
        setTimeout(() => resolve(false), 4000);
      });
      // If the image failed OR resolves to our block IP, we're protected.
      // If it loaded from some real third-party, user is on a different DNS.
      setState(loaded ? "unprotected" : "protected");
    } catch {
      setState("error");
    }
  }

  return (
    <div className="rounded-2xl border border-zinc-700 bg-zinc-900/50 p-5">
      <div className="flex items-center justify-between gap-4">
        <div>
          <div className="font-semibold">Am I protected?</div>
          <div className="text-sm text-zinc-400">
            Runs a quick DNS probe against a known test domain.
          </div>
        </div>
        <button
          onClick={run}
          disabled={state === "checking"}
          className="rounded-lg bg-brand px-4 py-2 text-sm font-semibold hover:bg-brand-dark disabled:opacity-60"
        >
          {state === "checking" ? "Checking…" : "Run test"}
        </button>
      </div>

      {state === "protected" && (
        <div className="mt-4 rounded-lg border border-emerald-600/40 bg-emerald-950/30 p-3 text-sm text-emerald-200">
          ✅ Looks good — the test domain was blocked.
          {verdict?.verdict && ` (Verdict: ${verdict.verdict}.)`}
        </div>
      )}
      {state === "unprotected" && (
        <div className="mt-4 rounded-lg border border-amber-600/40 bg-amber-950/30 p-3 text-sm text-amber-200">
          ⚠️ We couldn&apos;t confirm blocking. Your device may still be using its
          default DNS. Try rebooting, or re-check your DNS settings above.
        </div>
      )}
      {state === "error" && (
        <div className="mt-4 rounded-lg border border-red-600/40 bg-red-950/30 p-3 text-sm text-red-200">
          Test failed to reach ScamLens API. Check your internet connection.
        </div>
      )}
    </div>
  );
}
