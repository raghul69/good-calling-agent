/**
 * Centralized public env for Vite + Vercel.
 * Variables must use NEXT_PUBLIC_* (see vite.config.ts envPrefix).
 * Optional: `hydratePublicEnvFromApi()` may set globalThis.__JETTONE_PUBLIC_ENV_PATCH__
 * before this module loads (Supabase URL/anon from Railway).
 */

import { z } from "zod";

const LABEL = "[ENV]";

function getEnvPatch(): { NEXT_PUBLIC_SUPABASE_URL?: string; NEXT_PUBLIC_SUPABASE_ANON_KEY?: string } {
  const p = typeof globalThis !== "undefined" ? globalThis.__JETTONE_PUBLIC_ENV_PATCH__ : undefined;
  if (!p || typeof p !== "object") return {};
  return {
    NEXT_PUBLIC_SUPABASE_URL: typeof p.NEXT_PUBLIC_SUPABASE_URL === "string" ? p.NEXT_PUBLIC_SUPABASE_URL : undefined,
    NEXT_PUBLIC_SUPABASE_ANON_KEY:
      typeof p.NEXT_PUBLIC_SUPABASE_ANON_KEY === "string" ? p.NEXT_PUBLIC_SUPABASE_ANON_KEY : undefined,
  };
}

function readRawFromImportMeta(): Record<"NEXT_PUBLIC_SUPABASE_URL" | "NEXT_PUBLIC_SUPABASE_ANON_KEY" | "NEXT_PUBLIC_API_URL", string> {
  const isDev = Boolean(import.meta.env.DEV);
  const patch = getEnvPatch();
  return {
    NEXT_PUBLIC_SUPABASE_URL: (
      String(import.meta.env.NEXT_PUBLIC_SUPABASE_URL ?? "").trim() ||
      (isDev ? String(import.meta.env.VITE_SUPABASE_URL ?? "").trim() : "") ||
      String(patch.NEXT_PUBLIC_SUPABASE_URL ?? "").trim()
    ).trim(),
    NEXT_PUBLIC_SUPABASE_ANON_KEY: (
      String(import.meta.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "").trim() ||
      (isDev ? String(import.meta.env.VITE_SUPABASE_ANON_KEY ?? "").trim() : "") ||
      String(patch.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "").trim()
    ).trim(),
    NEXT_PUBLIC_API_URL: (
      String(import.meta.env.NEXT_PUBLIC_API_URL ?? "").trim() ||
      (isDev ? String(import.meta.env.VITE_API_URL ?? "").trim() : "")
    ).trim(),
  };
}

const supabaseUrlSchema = z
  .string()
  .trim()
  .min(1, "Missing NEXT_PUBLIC_SUPABASE_URL. Did you forget to set it in Vercel?")
  .refine((v) => /^https:\/\//i.test(v), {
    message: "NEXT_PUBLIC_SUPABASE_URL must be an https URL (your Supabase project URL).",
  });

const supabaseAnonSchema = z
  .string()
  .trim()
  .min(1, "Missing NEXT_PUBLIC_SUPABASE_ANON_KEY. Did you forget to set it in Vercel?");

const apiUrlSchema = z
  .string()
  .trim()
  .min(1, "Missing NEXT_PUBLIC_API_URL. Set it in Vercel to your Railway API base URL (no path, no trailing slash).")
  .refine(
    (v) => {
      try {
        const u = new URL(v);
        return u.protocol === "https:";
      } catch {
        return false;
      }
    },
    { message: "NEXT_PUBLIC_API_URL must be a valid https URL (e.g. https://your-service.up.railway.app)." },
  );

export type PublicEnv = {
  NEXT_PUBLIC_SUPABASE_URL: string;
  NEXT_PUBLIC_SUPABASE_ANON_KEY: string;
  NEXT_PUBLIC_API_URL: string;
};

const raw = readRawFromImportMeta();
const r1 = supabaseUrlSchema.safeParse(raw.NEXT_PUBLIC_SUPABASE_URL);
const r2 = supabaseAnonSchema.safeParse(raw.NEXT_PUBLIC_SUPABASE_ANON_KEY);
const r3 = apiUrlSchema.safeParse(raw.NEXT_PUBLIC_API_URL);

const messages: string[] = [];
if (!r1.success) messages.push(r1.error.issues[0]?.message ?? "Invalid NEXT_PUBLIC_SUPABASE_URL.");
if (!r2.success) messages.push(r2.error.issues[0]?.message ?? "Invalid NEXT_PUBLIC_SUPABASE_ANON_KEY.");
if (!r3.success) messages.push(r3.error.issues[0]?.message ?? "Invalid NEXT_PUBLIC_API_URL.");

export const envIssueMessages: readonly string[] = messages;

/** Each field validated independently; empty string if that field failed. */
export const env: PublicEnv = {
  NEXT_PUBLIC_SUPABASE_URL: r1.success ? r1.data : "",
  NEXT_PUBLIC_SUPABASE_ANON_KEY: r2.success ? r2.data : "",
  NEXT_PUBLIC_API_URL: r3.success ? r3.data.replace(/\/$/, "") : "",
};

export const isSupabaseConfigured = r1.success && r2.success;

export const isApiConfigured = r3.success;

/** Full triple — used for “fully configured app” banners / dev guard. */
export const isPublicEnvValid = isSupabaseConfigured && isApiConfigured;

if (!isPublicEnvValid && import.meta.env.PROD) {
  console.error(`${LABEL} Missing or invalid public env — some features disabled.\n${messages.join("\n")}`);
}

export const missingSupabaseEnvMessage =
  "Authentication is misconfigured: set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY in Vercel (see docs/VERCEL_PRODUCTION_CHECKLIST.md).";

export const missingApiEnvMessage =
  "Backend unreachable. In Vercel set NEXT_PUBLIC_API_URL to your HTTPS Railway API URL (see docs/VERCEL_PRODUCTION_CHECKLIST.md).";

export const appMisconfiguredUserMessage = "App is not configured. Please contact admin.";

/**
 * Call from `main.tsx` after `hydratePublicEnvFromApi()`. Skipped under Vitest (`MODE=test`).
 */
export function ensureDevEnvOrThrow(): void {
  if (isPublicEnvValid) return;
  if (!import.meta.env.DEV) return;
  if (import.meta.env.MODE === "test") return;
  throw new Error(`${LABEL} Invalid public environment:\n${messages.join("\n")}`);
}
