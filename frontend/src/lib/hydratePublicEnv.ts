/**
 * When Vercel omits Supabase NEXT_PUBLIC_* vars but NEXT_PUBLIC_API_URL is set,
 * pull public Supabase settings from Railway: GET /api/public/client-config
 * (must run before any module imports ./env).
 */

function readApiBaseFromImportMetaOnly(): string {
  const isDev = Boolean(import.meta.env.DEV);
  return (
    String(import.meta.env.NEXT_PUBLIC_API_URL ?? "").trim() ||
    (isDev ? String(import.meta.env.VITE_API_URL ?? "").trim() : "")
  ).trim();
}

function hasSupabaseFromImportMeta(): boolean {
  const isDev = Boolean(import.meta.env.DEV);
  const url = (
    String(import.meta.env.NEXT_PUBLIC_SUPABASE_URL ?? "").trim() ||
    (isDev ? String(import.meta.env.VITE_SUPABASE_URL ?? "").trim() : "")
  ).trim();
  const key = (
    String(import.meta.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "").trim() ||
    (isDev ? String(import.meta.env.VITE_SUPABASE_ANON_KEY ?? "").trim() : "")
  ).trim();
  return Boolean(url && key);
}

export async function hydratePublicEnvFromApi(): Promise<void> {
  if (import.meta.env.MODE === "test") return;
  if (hasSupabaseFromImportMeta()) return;

  const base = readApiBaseFromImportMetaOnly().replace(/\/$/, "");
  if (!base) return;

  try {
    const res = await fetch(`${base}/api/public/client-config`, { method: "GET", mode: "cors" });
    if (!res.ok) return;
    const data = (await res.json()) as {
      supabase_url?: string;
      supabase_anon_key?: string;
      configured?: boolean;
    };
    if (!data.configured || !data.supabase_url || !data.supabase_anon_key) return;
    globalThis.__JETTONE_PUBLIC_ENV_PATCH__ = {
      NEXT_PUBLIC_SUPABASE_URL: String(data.supabase_url).trim(),
      NEXT_PUBLIC_SUPABASE_ANON_KEY: String(data.supabase_anon_key).trim(),
    };
    if (import.meta.env.DEV) {
      console.info("[ENV] Hydrated Supabase public config from API (NEXT_PUBLIC_SUPABASE_* were empty).");
    }
  } catch {
    /* network / CORS — fall back to build-time env only */
  }
}
