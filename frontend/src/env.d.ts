/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Production/Vercel: required for API calls */
  readonly NEXT_PUBLIC_API_URL?: string;
  readonly NEXT_PUBLIC_SUPABASE_URL?: string;
  readonly NEXT_PUBLIC_SUPABASE_ANON_KEY?: string;
  /** Local dev fallback only (.env.development); production should use NEXT_PUBLIC_* */
  readonly VITE_API_URL?: string;
  readonly VITE_SUPABASE_URL?: string;
  readonly VITE_SUPABASE_ANON_KEY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

/** Filled by `hydratePublicEnvFromApi()` before `./lib/env` loads. */
interface JettonePublicEnvPatch {
  NEXT_PUBLIC_SUPABASE_URL?: string;
  NEXT_PUBLIC_SUPABASE_ANON_KEY?: string;
}

declare global {
  var __JETTONE_PUBLIC_ENV_PATCH__: JettonePublicEnvPatch | undefined;
}
