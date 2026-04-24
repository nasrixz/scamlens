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
    <SetupLayout active="windows" title="Windows 10 / 11">
      <ol className="list-decimal space-y-3 pl-6">
        <li>Open <strong>Settings</strong> → <strong>Network &amp; Internet</strong>.</li>
        <li>Select your active connection (Wi-Fi or Ethernet).</li>
        <li>Click <strong>Edit DNS settings</strong>.</li>
        <li>Change <em>Automatic</em> to <strong>Manual</strong>. Toggle IPv4 on.</li>
        <li>
          Set <strong>Preferred DNS</strong> to <code className="rounded bg-zinc-800 px-1.5 py-0.5">{serverIp}</code>.
        </li>
        <li>Leave <em>DNS encryption</em> on <strong>Encrypted only (DNS over HTTPS)</strong> if shown.</li>
        <li>Click <strong>Save</strong>.</li>
      </ol>

      <div className="rounded-xl border border-zinc-700 bg-zinc-900/50 p-5">
        <div className="text-sm text-zinc-400">
          Prefer DoH in the browser? Use this hostname in Firefox / Chrome secure-DNS settings:
        </div>
        <div className="mt-1 select-all font-mono text-lg">
          https://{hostname}/dns-query
        </div>
      </div>

      <h3 className="text-lg font-semibold">Quick set via PowerShell (admin)</h3>
      <pre className="overflow-x-auto rounded-xl border border-zinc-800 bg-zinc-900 p-4 text-sm">{`Set-DnsClientServerAddress -InterfaceAlias "Wi-Fi" -ServerAddresses ${serverIp}
Clear-DnsClientCache`}</pre>

      <VerifyWidget />

      <Troubleshoot
        items={[
          {
            q: "Windows still uses the old DNS.",
            a: <>Run <code className="rounded bg-zinc-800 px-1.5 py-0.5">ipconfig /flushdns</code>, disconnect/reconnect the network adapter, or reboot.</>,
          },
          {
            q: "Corporate VPN clobbers the DNS setting.",
            a: "VPN clients often push their own DNS. Configure ScamLens at the router level or on the VPN admin side.",
          },
          {
            q: "Browser ignores system DNS (Chrome / Edge / Firefox).",
            a: "Modern browsers use secure DNS by default. Turn it off or point it at the ScamLens DoH URL above.",
          },
        ]}
      />
    </SetupLayout>
  );
}
