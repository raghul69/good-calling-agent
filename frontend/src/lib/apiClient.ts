/**
 * Safe HTTP client for the Railway / FastAPI base URL.
 * Uses only NEXT_PUBLIC_API_URL (via ./env). Never sends server-only secrets.
 */

import { env, isApiConfigured } from "./env";
import { apiConnectionMessage, apiUnreachableMessage } from "./apiMessages";

export function getApiBaseUrl(): string {
  return env.NEXT_PUBLIC_API_URL.replace(/\/$/, "");
}

/** Full URL for a path beginning with `/`. */
export function resolveApiUrl(path: string): string {
  if (!path.startsWith("/")) {
    console.warn("[API] Expected path starting with /, got:", path);
  }
  const base = getApiBaseUrl();
  const p = path.startsWith("/") ? path : `/${path}`;
  return `${base}${p}`;
}

/**
 * `fetch` relative to NEXT_PUBLIC_API_URL. Logs a warning if the API base is not configured.
 */
export async function apiClientFetch(path: string, init: RequestInit = {}): Promise<Response> {
  if (!isApiConfigured) {
    console.warn("[API]", apiConnectionMessage);
    throw new Error(apiConnectionMessage);
  }
  const url = resolveApiUrl(path);
  try {
    return await fetch(url, { ...init, mode: "cors" });
  } catch {
    console.warn("[API]", apiUnreachableMessage);
    throw new Error(apiUnreachableMessage);
  }
}
