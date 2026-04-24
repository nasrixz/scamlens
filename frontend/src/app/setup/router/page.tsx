import { apiGet } from "@/lib/api";
import { SetupLayout } from "@/components/SetupLayout";
import { Troubleshoot } from "@/components/Troubleshoot";
import { VerifyWidget } from "@/components/VerifyWidget";

type Setup = { block_page_ip: string };

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
    <SetupLayout active="router" title="Router — protect every device at once">
      <p className="text-zinc-300">
        Change DNS on your router once, and every device on the network is
        protected — phones, TVs, consoles, IoT, guest devices. Menu wording
        differs by vendor; the DNS setting is usually under WAN, Internet,
        or DHCP.
      </p>

      <ol className="list-decimal space-y-3 pl-6">
        <li>Log into the router admin page (typically <code className="rounded bg-zinc-800 px-1.5 py-0.5">192.168.1.1</code> or <code className="rounded bg-zinc-800 px-1.5 py-0.5">192.168.0.1</code>).</li>
        <li>Find <strong>DNS</strong> settings — usually under <em>Internet</em>, <em>WAN</em>, or <em>DHCP Server</em>.</li>
        <li>Change DNS mode to <strong>Manual</strong> (or similar).</li>
        <li>
          Set <strong>Primary DNS</strong> to <code className="rounded bg-zinc-800 px-1.5 py-0.5">{serverIp}</code>.
          Clear any secondary DNS or set it to the same IP.
        </li>
        <li>Save and reboot the router.</li>
        <li>Reconnect a device to Wi-Fi (or wait for DHCP lease to refresh).</li>
      </ol>

      <div className="rounded-xl border border-amber-600/30 bg-amber-950/20 p-5 text-sm text-amber-200">
        If Android devices ignore router DNS, set Private DNS manually on each —
        see the Android page. Same for iOS with the Configuration Profile.
      </div>

      <h3 className="text-lg font-semibold">Where the DNS setting lives by vendor</h3>
      <div className="overflow-hidden rounded-xl border border-zinc-800">
        <table className="w-full text-left text-sm">
          <thead className="bg-zinc-900/60 text-xs uppercase text-zinc-500">
            <tr>
              <th className="px-4 py-2">Vendor</th>
              <th className="px-4 py-2">Menu path</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800">
            {VENDORS.map((v) => (
              <tr key={v.name}>
                <td className="px-4 py-2 font-medium">{v.name}</td>
                <td className="px-4 py-2 text-zinc-400">{v.path}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <VerifyWidget />

      <Troubleshoot
        items={[
          {
            q: "Router rejects the setting / reverts to ISP DNS.",
            a: "Some ISP-supplied routers lock DNS. Put the router in bridge mode and use your own, or set DNS per-device.",
          },
          {
            q: "Only the WAN DNS field exists, no LAN / DHCP DNS.",
            a: "Setting WAN DNS is enough on most consumer routers — the DHCP server automatically passes the same DNS to clients.",
          },
          {
            q: "Android 9+ phones still using ISP DNS.",
            a: "Private DNS on Android 9+ overrides DHCP. Set Private DNS to the ScamLens hostname on each device.",
          },
        ]}
      />
    </SetupLayout>
  );
}

const VENDORS = [
  { name: "TP-Link",   path: "Advanced → Network → Internet → use these DNS addresses" },
  { name: "Asus",      path: "WAN → Internet Connection → DNS Server → Manual" },
  { name: "Netgear",   path: "Internet → Domain Name Server (DNS) → Use these DNS servers" },
  { name: "Linksys",   path: "Connectivity → Internet Settings → Edit → Static DNS 1" },
  { name: "D-Link",    path: "Internet → Manual IPv4 Internet Connection Setup → Primary DNS" },
  { name: "UniFi",     path: "Settings → Networks → WAN → DNS Server" },
  { name: "pfSense",   path: "System → General Setup → DNS Server Settings" },
  { name: "MikroTik",  path: "IP → DNS → Servers" },
  { name: "OpenWrt",   path: "Network → Interfaces → WAN → Advanced Settings → Use custom DNS servers" },
  { name: "AT&T BGW",  path: "Home Network → Subnets & DHCP → Primary DNS" },
  { name: "Xfinity xFi",path: "Limited. Use IPv4 Static Leases or per-device setup." },
];
