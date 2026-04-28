import { supabase } from "./supabase";

const API_BASE_URL = (
  import.meta.env.NEXT_PUBLIC_API_URL ||
  import.meta.env.VITE_API_URL ||
  "https://good-calling-agent-production.up.railway.app"
).replace(/\/$/, "");

export type AnalyticsSummary = {
  total_calls: number;
  total_bookings: number;
  avg_duration: number;
  booking_rate: number;
};

export function apiUrl(path: string): string {
  if (!path.startsWith("/")) return path;
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

  if (!res.ok) {
    const message =
      typeof data === "object" && data && "detail" in data
        ? String((data as { detail: unknown }).detail)
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
  agents: () => apiFetchWithFallback<any[]>(["/api/agents"], []),
  calls: () => apiFetchWithFallback<any[]>(["/api/calls", "/api/logs"], []),
  campaigns: () => apiFetchWithFallback<any[]>(["/api/campaigns"], []),
  analytics: () =>
    apiFetchWithFallback<AnalyticsSummary>(["/api/analytics", "/api/stats"], {
      total_calls: 0,
      total_bookings: 0,
      avg_duration: 0,
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
};
