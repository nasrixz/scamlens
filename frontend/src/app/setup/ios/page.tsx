"use client";

import { QRCodeSVG } from "qrcode.react";
import { API_BASE } from "@/lib/api";
import { SetupLayout } from "@/components/SetupLayout";
import { Troubleshoot } from "@/components/Troubleshoot";
import { VerifyWidget } from "@/components/VerifyWidget";

export default function Page() {
  const profileUrl = `${API_BASE}/setup/ios`;
  return (
    <SetupLayout active="ios" title="iPhone / iPad — Configuration Profile">
      <p className="text-zinc-300">
        Tap the button below on your iPhone to install the DNS profile. Configures
        system-wide DNS-over-HTTPS. Works on every WiFi and cellular network.
      </p>

      <div className="flex flex-wrap items-center gap-6">
        <a
          href={profileUrl}
          className="rounded-xl bg-brand px-6 py-3 font-semibold text-white hover:bg-brand-dark"
        >
          Download profile
        </a>
        <div className="rounded-xl border border-zinc-700 bg-white p-3">
          <QRCodeSVG value={profileUrl} size={160} />
        </div>
        <div className="text-sm text-zinc-400">
          Open camera, point at the QR code, tap the link.
        </div>
      </div>

      <ol className="list-decimal space-y-2 pl-6 text-zinc-200">
        <li>Safari downloads the profile and shows a notice.</li>
        <li>Open Settings → General → VPN &amp; Device Management.</li>
        <li>Tap ScamLens Protection → Install. Enter your passcode.</li>
        <li>DNS is now routed through ScamLens on every connection.</li>
      </ol>

      <div className="rounded-xl border border-amber-600/30 bg-amber-950/20 p-5 text-sm text-amber-200">
        Profile is unsigned, so iOS shows a &quot;Not Signed&quot; notice. Verify the domain
        after install: Settings → General → VPN &amp; Device Management → ScamLens
        Protection. Remove any time from that screen.
      </div>

      <VerifyWidget />

      <Troubleshoot
        items={[
          {
            q: "Profile won't download in Safari.",
            a: "Tap the link inside Safari, not Chrome or in-app browsers. iOS only installs profiles from Safari/Mail/AirDrop.",
          },
          {
            q: "Install prompt never appears.",
            a: "Open Settings → General → VPN & Device Management and look under 'Downloaded Profile'.",
          },
          {
            q: "Some sites or corporate Wi-Fi stops working.",
            a: "Add your corp domain to the exemption list and regenerate the profile with --prohibited <domain>.",
          },
          {
            q: "How do I remove the profile?",
            a: "Settings → General → VPN & Device Management → ScamLens Protection → Remove Profile.",
          },
        ]}
      />
    </SetupLayout>
  );
}
