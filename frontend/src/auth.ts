export const ACCESS_TOKEN_KEY = "rx_access_token";
const API_BASE_URL = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");

export function apiUrl(path: string): string {
  if (!API_BASE_URL || !path.startsWith("/")) {
    return path;
  }
  return `${API_BASE_URL}${path}`;
}

export function getAccessToken(): string {
  return localStorage.getItem(ACCESS_TOKEN_KEY) || "";
}

export function setAccessToken(token: string): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, token);
}

export function clearAccessToken(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
}

export async function authFetch(input: RequestInfo | URL, init: RequestInit = {}) {
  const token = getAccessToken();
  const headers = new Headers(init.headers || {});
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const url = typeof input === "string" ? apiUrl(input) : input;
  return fetch(url, { ...init, headers });
}
