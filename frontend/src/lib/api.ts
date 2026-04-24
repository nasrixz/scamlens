export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000/api";

export async function apiGet<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    cache: "no-store",
    ...init,
  });
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
  return (await res.json()) as T;
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
  return (await res.json()) as T;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const fetcher = (path: string): Promise<any> => apiGet(path);

// --- Types ---------------------------------------------------------------

export type Stats = {
  total_blocked: number;
  blocked_today: number;
  unique_domains: number;
  top_domains: { domain: string; count: number }[];
  daily: { day: string; count: number }[];
};

export type BlockedRow = {
  id: number;
  domain: string;
  reason: string;
  verdict: string | null;
  ai_confidence: number | null;
  risk_score: number | null;
  mimics_brand: string | null;
  country: string | null;
  created_at: string;
};

export type BlockedPage = {
  items: BlockedRow[];
  total: number;
  page: number;
  page_size: number;
};

export type CheckResult = {
  domain: string;
  verdict: "safe" | "suspicious" | "scam" | "pending" | "unknown";
  risk_score: number | null;
  confidence: number | null;
  reason: string | null;
  mimics_brand: string | null;
  source: string;
  cached: boolean;
};
