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
  added_at: string;
};
