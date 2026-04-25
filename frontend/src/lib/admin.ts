import { API_BASE } from "./api";

// Admin API calls send cookies. Relies on same-origin HTTPS.

async function adminFetch<T>(
  path: string,
  init?: RequestInit & { json?: unknown },
): Promise<T> {
  const body = init?.json ? JSON.stringify(init.json) : init?.body;
  const headers: Record<string, string> = {
    ...(init?.headers as Record<string, string> | undefined),
  };
  if (init?.json) headers["content-type"] = "application/json";

  const res = await fetch(`${API_BASE}/admin${path}`, {
    ...init,
    body,
    headers,
    credentials: "include",
  });

  if (res.status === 401) throw new AdminAuthError();
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`admin ${path} → ${res.status} ${text}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export class AdminAuthError extends Error {
  constructor() {
    super("not authenticated");
  }
}

export const adminApi = {
  login: (email: string, password: string) =>
    adminFetch<{ email: string; role: string }>("/login", {
      method: "POST",
      json: { email, password },
    }),
  logout: () => adminFetch<{ ok: boolean }>("/logout", { method: "POST" }),
  me: () => adminFetch<{ id: number; email: string; role: string }>("/me"),
  counts: () =>
    adminFetch<{
      pending_reports: number;
      blocklist: number;
      whitelist: number;
      brands: number;
    }>("/counts"),
  listReports: (statusFilter: string) =>
    adminFetch<{ items: AdminReport[] }>(
      `/reports?status_filter=${statusFilter}`,
    ),
  confirmReport: (id: number) =>
    adminFetch<{ domain: string }>(`/reports/${id}/confirm`, { method: "POST" }),
  rejectReport: (id: number) =>
    adminFetch<{ id: number }>(`/reports/${id}/reject`, { method: "POST" }),
  listBlocklist: () =>
    adminFetch<{ items: DomainRow[] }>(`/blocklist?limit=500`),
  addBlocklist: (domain: string, reason?: string) =>
    adminFetch<{ domain: string }>("/blocklist", {
      method: "POST",
      json: { domain, reason },
    }),
  removeBlocklist: (domain: string) =>
    adminFetch(`/blocklist/${encodeURIComponent(domain)}`, { method: "DELETE" }),
  listWhitelist: () =>
    adminFetch<{ items: DomainRow[] }>(`/whitelist?limit=500`),
  addWhitelist: (domain: string, reason?: string) =>
    adminFetch<{ domain: string }>("/whitelist", {
      method: "POST",
      json: { domain, reason },
    }),
  removeWhitelist: (domain: string) =>
    adminFetch(`/whitelist/${encodeURIComponent(domain)}`, { method: "DELETE" }),
  scan: (url: string) =>
    adminFetch<ScanReport>("/scan", { method: "POST", json: { url } }),
  startScrape: (opts: {
    source?: "threads" | "reddit" | "urlhaus";
    keywords?: string[];
    duration_minutes?: number;
    max_pages?: number;
    subreddits?: string[];
  }) => adminFetch<{ status: string; source?: string; message?: string }>(
    "/scrape",
    { method: "POST", json: opts },
  ),
  scrapeStatus: () =>
    adminFetch<{ running: boolean; runs: ScrapeRun[] }>("/scrape/status"),
  scrapeSearch: (q: string, max_pages = 1) =>
    adminFetch<{ q: string; count: number; posts: ScrapeSearchPost[] }>(
      "/scrape/search",
      { method: "POST", json: { q, max_pages } },
    ),
};

export type ScrapeSearchPost = {
  id: string;
  username: string;
  permalink: string;
  media_type: string;
  is_reply: boolean;
  is_quote_post: boolean;
  text_preview: string;
  extracted_urls: string[];
};

export type ScrapeRun = {
  id: number;
  platform: string;
  started_at: string;
  finished_at: string | null;
  posts_seen: number;
  urls_seen: number;
  domains_new: number;
  domains_blocked: number;
  errors: number;
};

export type ScanReport = {
  domain: string;
  fetched: boolean;
  error?: string;
  empty_page?: boolean;
  empty_reason?: string;
  final_url?: string;
  status?: number;
  title?: string;
  html_excerpt?: string;
  screenshot_base64?: string;
  verdict?: {
    verdict: "safe" | "suspicious" | "scam";
    risk_score: number;
    confidence: number;
    reasons: string[];
    mimics_brand: string | null;
    model: string;
  };
  domain_age_days?: number | null;
  links?: {
    domain: string;
    first_seen_href: string;
    cached_verdict: {
      verdict?: string;
      risk_score?: number;
      source?: string;
    } | null;
  }[];
};

export type AdminReport = {
  id: number;
  domain: string;
  note: string | null;
  status: string;
  reporter_ip: string | null;
  created_at: string;
};

export type DomainRow = {
  domain: string;
  category?: string | null;
  reason?: string | null;
  added_by?: string | null;
  source_post?: string | null;
  source_platform?: string | null;
  added_at: string;
};
