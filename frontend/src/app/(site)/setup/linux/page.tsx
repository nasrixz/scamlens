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

  return (
    <SetupLayout active="linux" title="Linux">
      <h3 className="text-lg font-semibold">NetworkManager (GNOME, KDE, most distros)</h3>
      <pre className="overflow-x-auto rounded-xl border border-zinc-800 bg-zinc-900 p-4 text-sm">{`# list connections
nmcli con show

# point the active connection at ScamLens (replace 'Wired connection 1')
nmcli con mod "Wired connection 1" ipv4.dns "${serverIp}" ipv4.ignore-auto-dns yes
nmcli con up "Wired connection 1"`}</pre>

      <h3 className="text-lg font-semibold">systemd-resolved</h3>
      <pre className="overflow-x-auto rounded-xl border border-zinc-800 bg-zinc-900 p-4 text-sm">{`sudo tee /etc/systemd/resolved.conf.d/scamlens.conf <<EOF
[Resolve]
DNS=${serverIp}
DNSStubListener=yes
Domains=~.
EOF
sudo systemctl restart systemd-resolved`}</pre>

      <h3 className="text-lg font-semibold">Plain /etc/resolv.conf</h3>
      <pre className="overflow-x-auto rounded-xl border border-zinc-800 bg-zinc-900 p-4 text-sm">{`# Only if you don't run NetworkManager / resolved.
sudo sh -c 'echo "nameserver ${serverIp}" > /etc/resolv.conf'`}</pre>

      <p className="text-sm text-zinc-400">
        Verify: <code className="rounded bg-zinc-800 px-1.5 py-0.5">dig paypa1.com</code> — answer
        should be <code className="rounded bg-zinc-800 px-1.5 py-0.5">{serverIp}</code>.
      </p>

      <VerifyWidget />

      <Troubleshoot
        items={[
          {
            q: "/etc/resolv.conf keeps getting overwritten.",
            a: "A DHCP client or NetworkManager is managing it. Use the NetworkManager or systemd-resolved method above instead — resolv.conf edits won't stick.",
          },
          {
            q: "dig still shows 127.0.0.53.",
            a: "That's systemd-resolved's stub. It proxies your configured DNS — check `resolvectl status` to confirm the upstream is ScamLens.",
          },
          {
            q: "Firefox has its own DoH that bypasses system DNS.",
            a: <>Disable or point it at the ScamLens DoH URL: Preferences → Privacy &amp; Security → DNS over HTTPS → Custom.</>,
          },
        ]}
      />
    </SetupLayout>
  );
}
