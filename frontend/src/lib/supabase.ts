import { createClient } from "@supabase/supabase-js";

const FALLBACK_SUPABASE_URL = "https://example.supabase.co";
const FALLBACK_SUPABASE_ANON_KEY = "missing-anon-key";

const urlRaw = (
  import.meta.env.NEXT_PUBLIC_SUPABASE_URL ||
  import.meta.env.VITE_SUPABASE_URL ||
  ""
).trim();
const keyRaw = (
  import.meta.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ||
  import.meta.env.VITE_SUPABASE_ANON_KEY ||
  ""
).trim();

export const isSupabaseConfigured = Boolean(urlRaw && keyRaw);

export const supabase = createClient(urlRaw || FALLBACK_SUPABASE_URL, keyRaw || FALLBACK_SUPABASE_ANON_KEY, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
  },
});

export function getAuthRedirectUrl(path = "/agents") {
  return `${window.location.origin}${path}`;
}
