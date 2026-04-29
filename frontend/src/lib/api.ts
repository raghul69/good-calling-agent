import { supabase } from "./supabase";

const apiBaseUrlRaw = (import.meta.env.NEXT_PUBLIC_API_URL || "").trim();
const API_BASE_URL = apiBaseUrlRaw.replace(/\/$/, "");

export const isApiConfigured = Boolean(API_BASE_URL);
export const apiConnectionMessage = "Backend not connected. Add NEXT_PUBLIC_API_URL in Vercel production env.";

export type AnalyticsSummary = {
  total_calls: number;
  answered_calls: number;
  failed_calls: number;
  total_bookings: number;
  avg_duration: number;
  average_duration: number;
  total_minutes: number;
  estimated_ai_cost: number;
  booking_rate: number;
};

export type CallNowResponse = {
  call_id: string;
  dispatch_id?: string;
  room_name: string;
  status: string;
  phone_number: string;
};

export type CurrentUser = {
  success: boolean;
  user_id?: string;
  email?: string;
  role?: string;
  roles?: string[];
  workspace_id?: string | null;
  workspace_created?: boolean;
};

export type WorkspaceSummary = {
  id: string | null;
  name: string;
  role: string;
  member_count: number;
  settings: Record<string, unknown>;
};

export type BillingSummary = {
  plan: string;
  status: string;
  included_minutes: number;
  used_minutes: number;
  overage_minutes: number;
  estimated_ai_cost: number;
  next_invoice_estimate: number;
};

export type Campaign = {
  id?: string;
  name: string;
  status?: string;
  total_calls?: number;
  completed_calls?: number;
  created_at?: string;
};

export function apiUrl(path: string): string {
  if (!path.startsWith("/")) return path;
  if (!isApiConfigured) {
    throw new Error(apiConnectionMessage);
  }
  return `${API_BASE_URL}${path}`;
}

export async function getAccessToken(): Promise<string> {
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token || "";
}

export async function signOut(): Promise<void> {
  await supabase.auth.signOut();
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  if (!isApiConfigured) {
    throw new Error(apiConnectionMessage);
  }
  const token = await getAccessToken();
  const headers = new Headers(init.headers || {});
  headers.set("Accept", "application/json");
  if (!(init.body instanceof FormData) && init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const res = await fetch(apiUrl(path), {
    ...init,
    headers,
    mode: "cors",
  });

  const contentType = res.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await res.json() : await res.text();

  if (path.startsWith("/api/") && !contentType.includes("application/json")) {
    throw new Error(`Backend route not connected: ${path}`);
  }

  if (!res.ok) {
    if (res.status === 401) {
      await supabase.auth.signOut();
    }
    const message = typeof data === "object" && data
      ? String(
          (data as any).error?.message ||
          (data as any).detail ||
          (data as any).message ||
          `API request failed: ${res.status}`,
        )
      : `API request failed: ${res.status}`;
    throw new Error(message);
  }

  return data as T;
}

export async function apiFetchWithFallback<T>(paths: string[], fallback: T): Promise<T> {
  for (const path of paths) {
    try {
      return await apiFetch<T>(path);
    } catch (error) {
      if (import.meta.env.DEV && path === paths[paths.length - 1]) {
        console.warn(`API fallback used after ${paths.join(", ")} failed`, error);
      }
    }
  }
  return fallback;
}

export const api = {
  health: () => apiFetch<Record<string, unknown>>("/api/health"),
  me: () => apiFetch<CurrentUser>("/api/auth/me"),
  workspace: () => apiFetch<WorkspaceSummary>("/api/workspace"),
  billing: () => apiFetch<BillingSummary>("/api/billing"),
  agents: () => apiFetchWithFallback<any[]>(["/api/agents"], []),
  calls: () => apiFetchWithFallback<any[]>(["/api/calls", "/api/logs"], []),
  campaigns: () => apiFetchWithFallback<Campaign[]>(["/api/campaigns"], []),
  analytics: () =>
    apiFetchWithFallback<AnalyticsSummary>(["/api/analytics", "/api/stats"], {
      total_calls: 0,
      answered_calls: 0,
      failed_calls: 0,
      total_bookings: 0,
      avg_duration: 0,
      average_duration: 0,
      total_minutes: 0,
      estimated_ai_cost: 0,
      booking_rate: 0,
    }),
  contacts: () => apiFetchWithFallback<any[]>(["/api/contacts"], []),
  config: () => apiFetch<Record<string, unknown>>("/api/config"),
  saveConfig: (config: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/api/config", {
      method: "POST",
      body: JSON.stringify(config),
    }),
  demoToken: () => apiFetch<{ token?: string; room?: string; url?: string; error?: string }>("/api/demo-token"),
  callNow: (phone_number: string, agent_id?: string) =>
    apiFetch<CallNowResponse>("/call", {
      method: "POST",
      body: JSON.stringify({ phone_number, agent_id }),
    }),
};
