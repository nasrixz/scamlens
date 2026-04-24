import { apiGet } from "@/lib/api";
import { SetupLayout } from "@/components/SetupLayout";
import { Troubleshoot } from "@/components/Troubleshoot";
import { VerifyWidget } from "@/components/VerifyWidget";

type Setup = {
  platform: string;
  dns_hostname: string;
  steps: string[];
  notes: string[];
};

async function getSetup(): Promise<Setup | null> {
  try {
    return await apiGet<Setup>("/setup/android");
  } catch {
    return null;
  }
}

export default async function Page() {
  const s = await getSetup();
  const hostname = s?.dns_hostname ?? "dns.example.com";

  return (
    <SetupLayout active="android" title="Android — Private DNS">
      <p className="text-zinc-300">
        Android 9 (Pie) and newer support system-wide encrypted DNS. No app needed.
      </p>

      <ol className="list-decimal space-y-3 pl-6">
        {(s?.steps ?? []).map((step, i) => (
          <li key={i}>{step}</li>
        ))}
      </ol>

      <div className="rounded-xl border border-zinc-700 bg-zinc-900/50 p-5">
        <div className="text-sm text-zinc-400">Private DNS hostname</div>
        <div className="mt-1 select-all font-mono text-lg">{hostname}</div>
      </div>

      {s?.notes?.length ? (
        <div className="rounded-xl border border-amber-600/30 bg-amber-950/20 p-5 text-sm text-amber-200">
          <ul className="list-disc space-y-1 pl-5">
            {s.notes.map((n, i) => (
              <li key={i}>{n}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <VerifyWidget />

      <Troubleshoot
        items={[
          {
            q: "Private DNS option is missing.",
            a: "Your Android version is older than 9 (Pie). Either update, or use a third-party DNS-over-HTTPS client app.",
          },
          {
            q: "Private DNS says 'Can't connect'.",
            a: "Mobile carrier or public Wi-Fi may block port 853. Switch to a different network and re-test.",
          },
          {
            q: "Some sites won't load after enabling.",
            a: "Clear the Android DNS cache: toggle airplane mode on/off, or restart the device.",
          },
          {
            q: "Does this work in mobile data (LTE/5G)?",
            a: "Yes. Private DNS applies on every network.",
          },
        ]}
      />
    </SetupLayout>
  );
}
