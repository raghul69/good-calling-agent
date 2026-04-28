import { createClient } from "@supabase/supabase-js";

const supabaseUrl = import.meta.env.NEXT_PUBLIC_SUPABASE_URL || "";
const supabaseAnonKey = import.meta.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "";

if (!supabaseUrl || !supabaseAnonKey) {
  console.warn("Supabase browser env vars are missing. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY.");
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
  },
});

export function getAuthRedirectUrl(path = "/dashboard") {
  return `${window.location.origin}${path}`;
}
