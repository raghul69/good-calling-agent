export const ACCESS_TOKEN_KEY = "rx_access_token";

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
  return fetch(input, { ...init, headers });
}
