/**
 * Supabase browser client. Only real credentials when Zod-validated public env is complete.
 * If env is invalid, a placeholder client is still created so importing modules never throws;
 * call sites must check `isSupabaseConfigured` before auth (see Login, api.getAccessToken).
 */

import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { env, isSupabaseConfigured, missingSupabaseEnvMessage } from "./env";

// Public demo placeholder — not used for network calls when isSupabaseConfigured is false.
const PLACEHOLDER_URL = "https://placeholder.supabase.co";
const PLACEHOLDER_ANON = "placeholder.supabase.anon.key";

const url = isSupabaseConfigured ? env.NEXT_PUBLIC_SUPABASE_URL : PLACEHOLDER_URL;
const key = isSupabaseConfigured ? env.NEXT_PUBLIC_SUPABASE_ANON_KEY : PLACEHOLDER_ANON;

export const supabase: SupabaseClient = createClient(url, key, {
  auth: {
    persistSession: Boolean(isSupabaseConfigured),
    autoRefreshToken: Boolean(isSupabaseConfigured),
    detectSessionInUrl: Boolean(isSupabaseConfigured),
  },
});

export { isSupabaseConfigured, missingSupabaseEnvMessage };

export function getAuthRedirectUrl(path = "/agents") {
  return `${window.location.origin}${path}`;
}
