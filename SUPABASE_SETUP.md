# Supabase Setup

Keep `SUPABASE_SERVICE_ROLE_KEY` server-side only. Put it in `.env` locally and Railway environment variables in production.

## Required Railway Variables

- `SUPABASE_URL`
- `SUPABASE_KEY`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_S3_ACCESS_KEY`
- `SUPABASE_S3_SECRET_KEY`
- `SUPABASE_S3_ENDPOINT`
- `SUPABASE_S3_REGION`

## Migrations

Run these in the Supabase SQL Editor:

1. `supabase_migration_v2.sql`
2. `supabase_migration_saas_workspaces.sql`
3. `supabase_migration_production_hardening.sql`
4. `supabase_migration_agent_foundation.sql`

The agent foundation migration adds workspace-scoped agents, immutable agent versions, provider routes, provider usage events, audit logs, and `call_logs.agent_version_id`.

## Auth URLs (Vercel + Railway + local)

Set **Site URL** to your deployed SPA (typically Vercel):

```text
https://YOUR_VERCEL_APP.vercel.app
```

Add **Redirect URLs** (include wildcards for hash / PKCE flows):

```text
https://YOUR_VERCEL_APP.vercel.app/**
https://YOUR_RAILWAY_PUBLIC_HOST.up.railway.app/**
http://localhost:3000/**
http://127.0.0.1:3000/**
http://localhost:5173/**
http://127.0.0.1:5173/**
```

Railway remains the API source of truth (`NEXT_PUBLIC_API_URL` on Vercel).

## MVP: email/password without confirmation (testing)

In Supabase Dashboard → **Authentication → Providers → Email**:

- Enable **Email** provider.
- For quick MVP / internal testing: **disable “Confirm email”** (or equivalent) so password signup signs in immediately — re-enable confirmation before public launch.

Continue to use **password** sign-in from the app (`Login.tsx`). OTP / magic link can stay available or be hidden in the UI; they are independent of this setting.

## Production email verification (recommended before public launch)

- Re-enable **Confirm email** for verified signup.
- Optionally keep **Email OTP / Magic Link** for passwordless login.

## Google OAuth

In Supabase Dashboard → Authentication → Providers → Google:

- Enable Google provider.
- Add the Google OAuth Client ID and Client Secret.
- In Google Cloud Console, add the Supabase callback URL shown in the Supabase Google provider settings.

The frontend uses:

```ts
supabase.auth.signInWithOAuth({
  provider: "google",
  options: { redirectTo: "https://YOUR_FRONTEND_OR_RAILWAY_DOMAIN/agents" },
});
```

## Production Rule

Use Railway as the backend source of truth. Vercel should call Railway through `NEXT_PUBLIC_API_URL`.
