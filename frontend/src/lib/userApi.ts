import { API_BASE } from "./api";

async function authFetch<T>(
  path: string,
  init?: RequestInit & { json?: unknown },
): Promise<T> {
  const headers: Record<string, string> = {
    ...(init?.headers as Record<string, string> | undefined),
  };
  let body: BodyInit | null | undefined = init?.body as BodyInit | undefined;
  if (init?.json !== undefined) {
    headers["content-type"] = "application/json";
    body = JSON.stringify(init.json);
  }
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    body,
    headers,
    credentials: "include",
  });
  if (res.status === 401) throw new AuthError();
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${path} → ${res.status} ${text.slice(0, 200)}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export class AuthError extends Error {
  constructor() {
    super("not authenticated");
  }
}

export type User = {
  id: number;
  email: string;
  role: "user" | "admin";
  invite_code: string;
  doh_token?: string;
  dns_hostname?: string;
};

export type Link = {
  link_id: number;
  other_id: number;
  other_email: string;
  other_invite_code: string;
  role_in_link: "guardian" | "ward";
  status: "pending" | "accepted" | "rejected" | "revoked";
  invited_at: string;
  responded_at: string | null;
};

export type DependentsResponse = {
  self: { id: number; email: string; invite_code: string };
  wards: Link[];
  guardians: Link[];
  pending_outgoing: Link[];
  pending_incoming: Link[];
};

export const userApi = {
  register: (email: string, password: string, display_name?: string) =>
    authFetch<User>("/auth/register", {
      method: "POST",
      json: { email, password, display_name },
    }),
  login: (email: string, password: string) =>
    authFetch<User>("/auth/login", {
      method: "POST",
      json: { email, password },
    }),
  logout: () => authFetch<{ ok: boolean }>("/auth/logout", { method: "POST" }),
  me: () => authFetch<User>("/auth/me"),
  dependents: () => authFetch<DependentsResponse>("/me/dependents"),
  invite: (invite_code: string) =>
    authFetch<{ link_id: number; status: string; ward_email: string }>(
      "/me/dependents/invite",
      { method: "POST", json: { invite_code } },
    ),
  accept: (linkId: number) =>
    authFetch<{ link_id: number; status: string }>(
      `/me/dependents/${linkId}/accept`,
      { method: "POST" },
    ),
  reject: (linkId: number) =>
    authFetch<{ link_id: number; status: string }>(
      `/me/dependents/${linkId}/reject`,
      { method: "POST" },
    ),
  revoke: (linkId: number) =>
    authFetch<{ link_id: number; removed: boolean }>(
      `/me/dependents/${linkId}`,
      { method: "DELETE" },
    ),
  myBlocks: (limit = 50) =>
    authFetch<{ items: BlockEvent[] }>(`/me/blocks?limit=${limit}`),
};

export type BlockEvent = {
  id: number;
  domain: string;
  reason: string;
  verdict: string | null;
  risk_score: number | null;
  ai_confidence: number | null;
  mimics_brand: string | null;
  resolved_ip: string | null;
  user_id: number | null;
  created_at: string;
};
