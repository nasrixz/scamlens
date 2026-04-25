"use client";

import useSWR from "swr";
import { fetcher } from "@/lib/api";

type Geo = {
  success: boolean;
  ip?: string;
  country?: string;
  country_code?: string;
  region?: string;
  city?: string;
  flag_emoji?: string;
  timezone?: string;
  connection?: {
    asn?: number;
    org?: string;
    isp?: string;
    domain?: string;
  };
  message?: string;
};

export function GeoLine({ ip }: { ip: string }) {
  const { data, error } = useSWR<Geo>(`/geo/${ip}`, fetcher, {
    revalidateOnFocus: false,
    dedupingInterval: 60_000,
  });

  if (error) return <div className="text-zinc-500">Geo lookup failed.</div>;
  if (!data) return <div className="text-zinc-500">Looking up origin…</div>;
  if (!data.success) {
    return (
      <div className="text-zinc-500">
        Origin: {data.message ?? "private / unroutable"}
      </div>
    );
  }

  const place = [data.city, data.region, data.country].filter(Boolean).join(", ");
  const conn = data.connection ?? {};
  const asn = conn.asn ? `AS${conn.asn}` : null;
  const isp = conn.isp || conn.org;

  return (
    <div className="text-zinc-400">
      <div>
        <span className="text-zinc-500">Origin:</span>{" "}
        {data.flag_emoji ?? ""} {place || "unknown"}
      </div>
      {(asn || isp) && (
        <div>
          <span className="text-zinc-500">Hosted by:</span> {isp ?? "—"}
          {asn ? ` (${asn})` : ""}
        </div>
      )}
    </div>
  );
}
