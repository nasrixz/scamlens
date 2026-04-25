import { apiGet } from "@/lib/api";
import { SetupLayout } from "@/components/SetupLayout";
import { Troubleshoot } from "@/components/Troubleshoot";
import { VerifyWidget } from "@/components/VerifyWidget";

type Setup = { block_page_ip: string; dns_hostname: string };

async function getSetup(): Promise<Setup | null> {
  try {
    return await apiGet<Setup>("/setup/desktop");
  } catch {
    return null;
  }
}

export default async function Page() {
  const s = await getSetup();
  const serverIp = s?.block_page_ip ?? "<your server IP>";
  const hostname = s?.dns_hostname ?? "dns.example.com";

  return (
    <SetupLayout active="macos" title="macOS">
      <p className="text-zinc-300">
        Recommended: install the <a href="/setup/ios" className="text-brand hover:underline">iOS Configuration Profile</a>.
        macOS accepts the same profile and enables DNS-over-HTTPS system-wide —
        encrypted and harder to bypass than raw DNS.
      </p>

      <h3 className="text-lg font-semibold">Or configure DNS manually</h3>
      <ol className="list-decimal space-y-3 pl-6">
        <li>Open <strong>System Settings</strong> → <strong>Network</strong>.</li>
        <li>Select your active interface (Wi-Fi or Ethernet) → <strong>Details…</strong></li>
        <li>Go to the <strong>DNS</strong> tab.</li>
        <li>
          Click <strong>+</strong> under DNS Servers and add:{" "}
          <code className="rounded bg-zinc-800 px-1.5 py-0.5">{serverIp}</code>
        </li>
        <li>Remove other servers so queries go only to ScamLens, then click <strong>OK</strong>.</li>
      </ol>

      <div className="rounded-xl border border-zinc-700 bg-zinc-900/50 p-5">
        <div className="text-sm text-zinc-400">DoH endpoint for browser-level setup:</div>
        <div className="mt-1 select-all font-mono text-lg">
          https://{hostname}/dns-query
        </div>
      </div>

      <h3 className="text-lg font-semibold">Terminal alternative</h3>
      <pre className="overflow-x-auto rounded-xl border border-zinc-800 bg-zinc-900 p-4 text-sm">{`networksetup -setdnsservers Wi-Fi ${serverIp}
dscacheutil -flushcache
sudo killall -HUP mDNSResponder`}</pre>

      <VerifyWidget />

      <Troubleshoot
        items={[
          {
            q: "Profile install dialog never appears.",
            a: "macOS downloads the profile to System Settings → Privacy & Security → Profiles. Open it from there.",
          },
          {
            q: "DNS setting reverts after reboot.",
            a: "The active network service might differ from 'Wi-Fi'. Run `networksetup -listallnetworkservices` and repeat with your actual interface name.",
          },
          {
            q: "Safari caches scam-domain lookups.",
            a: "Clear with: Develop menu → Empty Caches, or relaunch Safari.",
          },
        ]}
      />
    </SetupLayout>
  );
}
