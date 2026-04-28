import { apiFetch, apiUrl, getAccessToken, signOut } from "./lib/api";

export { apiUrl, getAccessToken };

export async function authFetch(input: RequestInfo | URL, init: RequestInit = {}) {
  if (typeof input !== "string") {
    return fetch(input, init);
  }
  const token = await getAccessToken();
  const headers = new Headers(init.headers || {});
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return fetch(apiUrl(input), { ...init, headers, mode: "cors" });
}

export async function clearAccessToken(): Promise<void> {
  await signOut();
}

export { apiFetch };
