# Vercel production checklist — Jettone frontend

This repo’s UI is built with **Vite + React** under `InboundAIVoice/frontend`. Env vars named `NEXT_PUBLIC_*` mirror Vercel/Next conventions, but **Vite only exposes prefixed keys if** `vite.config.ts` declares `envPrefix: ["VITE_", "NEXT_PUBLIC_"]`. This project includes that wiring.

## 1. Vercel environment (required)

Set these at **Vercel → Project → Settings → Environment Variables** for **Production** (and Preview if you use previews):

| Variable | Purpose |
|----------|---------|
| `NEXT_PUBLIC_API_URL` | HTTPS base URL for the Railway (or other) API, **no trailing slash** (example: `https://your-service.up.railway.app`). |
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase project URL. |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anonymous (public) key for browser auth. |

Local dev fallback (optional, **dev only**): `VITE_API_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` in `.env` if you prefer the default Vite naming.

Production builds rely on **`NEXT_PUBLIC_*`**; missing values surface as inline warnings and checklist messages in `api.ts` / `supabase.ts`.

## 2. Railway backend — CORS

The browser calls the API origin set in `NEXT_PUBLIC_API_URL`. Ensure your API **allows** your Vercel origin(s):

- Production: exact site origin, e.g. `https://your-app.vercel.app`.
- Previews (optional): wildcard or per-preview origins as your stack supports (`https://*-your-team.vercel.app` patterns only if explicitly configured and safe).

The corresponding server env is typically **`CORS_ORIGIN`** (or equivalent) on Railway — mirror the exact HTTPS origin string Vercel uses.

## 3. Supabase — Auth redirect URLs

In **Supabase Dashboard → Authentication → URL configuration**:

- Add your **production** site URL (`https://...vercel.app` or custom domain).
- Add **additional redirect URLs** for OAuth/password flows matching what the app calls from `window.location.origin` (and preview URLs if needed).

Misconfigured redirects usually show as stalled login or redirects to `/` without a session.

## 4. Smoke test after deploy

1. Open landing page → responsive layout, links to login.
2. **Login** → session established (Supabase).
3. **Dashboard** → stats and health/integration pills load without a persistent error banner.
4. **Agents** → agent list loads; create/save/publish behaves as expected.
5. **Test call path** → browser/SIP/outbound flows as wired in your Phase-0 rollout (respect LiveKit microphone permissions).
6. **Call History** (`/logs`) → list loads or intentional empty state if no calls logged yet.

Spot-check layout at **narrow width** (~390px): Chrome device toolbar / iPhone size — no sideways scroll on dashboard shell and lists.

## 5. Frontend production risks (shortlist)

| Risk | Mitigation |
|------|------------|
| Wrong or missing **`NEXT_PUBLIC_API_URL`** | Check Vercel env; Railway API reachable over HTTPS; CORS allows Vercel origin. |
| Wrong **`vite` `envPrefix`** | Repo keeps `NEXT_PUBLIC_*` in `vite.config.ts` — avoid removing or builds will strip client env. |
| **CORS drift** between preview and prod | Maintain separate Preview env or broadened `CORS_ORIGIN` intentionally. |
| **Supabase redirects** mismatch | Align Dashboard redirect allowlist with every deployed hostname. |
| **LiveKit** browser permissions | Tests need mic/speaker allowances; HTTPS required for secure contexts. |

## 6. Out of scope (known beta / follow-ups)

Multi-tenant org switcher, billing UI expansion, strict RLS-driven client reads everywhere, and other full-SaaS hardening remain separate workstreams beyond this frontend hardening pass.
