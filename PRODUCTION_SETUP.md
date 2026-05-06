# Production Setup

This project uses **Railway for the production backend / voice worker** and **Vercel for the frontend**.

Railway runs one Docker image with:

- FastAPI backend
- LiveKit worker via `supervisord`

Do not use Render for this project.

## 1. Supabase

Run these migrations in the Supabase SQL Editor in order:

1. `supabase_migration_v2.sql`
2. `supabase_migration_saas_workspaces.sql`
3. `supabase_migration_production_hardening.sql`
4. `supabase_migration_agent_foundation.sql`

The agent foundation migration adds workspace-scoped agents, immutable agent versions, provider routes, provider usage events, audit logs, and `call_logs.agent_version_id`.

Auth settings (see [`SUPABASE_SETUP.md`](SUPABASE_SETUP.md) for templates):

- Authentication → URL Configuration → **Site URL** (Vercel SPA): `https://YOUR_VERCEL_FRONTEND.vercel.app`
- Authentication → URL Configuration → **Redirect URLs**: `https://YOUR_VERCEL_FRONTEND.vercel.app/**`, `https://YOUR_RAILWAY_SERVICE.up.railway.app/**`, `http://localhost:3000/**`, `http://127.0.0.1:3000/**`, `http://localhost:5173/**`, `http://127.0.0.1:5173/**`
- Preview Vercel deploys: add host patterns for preview URLs you use with production API, or use a staging Supabase project.

**Railway + Vercel URL checklist**

| Dashboard | Setting | Typical value |
|-----------|---------|----------------|
| Supabase Auth | Site URL | `https://YOUR_VERCEL_APP.vercel.app` |
| Supabase Auth | Redirect URLs | Vercel + Railway `/**`; localhost 3000 + 5173 |
| Railway | `PUBLIC_APP_URL` | Canonical Vercel production URL |
| Railway | `CORS_ORIGIN` | Comma-separated browser origins |

- Authentication → Providers → **Email**: enable; for MVP you may **disable Confirm email** (re-enable before public launch).
- Authentication → Providers → **Google**: optional OAuth.
Required Supabase variables in Railway:

- `SUPABASE_URL`
- `SUPABASE_KEY`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_S3_ACCESS_KEY`
- `SUPABASE_S3_SECRET_KEY`
- `SUPABASE_S3_ENDPOINT`
- `SUPABASE_S3_REGION`

## 2. Railway Backend Deploy

Use the repo folder that contains `Dockerfile`, `backend/`, `frontend/`, `railway.toml`, and `supervisord.conf`.

Railway should detect:

- Build: `Dockerfile`
- Blueprint: [`railway.toml`](railway.toml) (healthcheck `GET /health`)
- Start command: Docker `CMD`, which runs `supervisord` (see `Dockerfile`; do not strip `supervisor` dependency)
- Health check: `/health`

Deploy steps:

1. Railway Dashboard -> New Project -> Deploy from GitHub repo.
2. Select the repo and branch, usually `main`.
3. If this repo is nested, set Railway Root Directory to `InboundAIVoice`.
4. Do not override the start command unless you intentionally replace `supervisord`.
5. Generate a Railway public domain.
6. Add variables from `env.railway.example`.
7. Push to the connected branch to redeploy.

Core Railway variables:

- `LIVEKIT_URL`
- `LIVEKIT_API_KEY`
- `LIVEKIT_API_SECRET`
- `LIVEKIT_SIP_TRUNK_ID` or `OUTBOUND_TRUNK_ID`
- `OPENAI_API_KEY`
- `GROQ_API_KEY`
- `SARVAM_API_KEY`
- `CAL_API_KEY`
- `CAL_EVENT_TYPE_ID`
- `CORS_ORIGIN` (comma-separated; include Vercel production + `http://localhost:3000` / `127.0.0.1` / `5173` as needed)
- Optional: `CORS_ORIGIN_REGEX` — set to `disabled` to turn off built-in Vercel preview regex only
- `PUBLIC_APP_URL`
Health checks after deploy:

```text
https://YOUR_RAILWAY_SERVICE.up.railway.app/health
https://YOUR_RAILWAY_SERVICE.up.railway.app/api/health
https://YOUR_RAILWAY_SERVICE.up.railway.app/api/livekit/health
https://YOUR_RAILWAY_SERVICE.up.railway.app/api/sip/health
```

Expected readiness:

- `supabase.configured: true`
- `supabase.service_role_key_present: true`
- `livekit.configured: true`
- `livekit.url_valid: true`
- SIP health `ok: true` before phone-call tests

## 3. Vercel Frontend

If the frontend is deployed separately on Vercel:

- Root Directory: `frontend`
- Repo: `frontend/vercel.json` (Vite framework, builds `dist`, SPA rewrites to `index.html`)
- Repo: `frontend/.env.example` (copy names into Vercel env vars)
- Build Command: `npm install && npm run build`
- Output Directory: `dist`
- Environment variable:
  - `NEXT_PUBLIC_API_URL=https://YOUR_RAILWAY_SERVICE.up.railway.app`
  - `NEXT_PUBLIC_SUPABASE_URL=https://YOUR_SUPABASE_PROJECT.supabase.co`
  - `NEXT_PUBLIC_SUPABASE_ANON_KEY=YOUR_SUPABASE_ANON_KEY`

Without `NEXT_PUBLIC_API_URL`, login/dashboard API calls will hit the frontend domain and return HTML instead of backend JSON.

Auth flows available from the login page:

- Password login.
- Password signup with email/Gmail verification.
- Email OTP login.
- Google OAuth login.

## 4. Stripe Billing

Set these Railway variables before using the Billing page checkout:

- `STRIPE_SECRET_KEY`
- `STRIPE_PRICE_ID`
- `STRIPE_WEBHOOK_SECRET`
- `PUBLIC_APP_URL`

Create a Stripe webhook endpoint:

```text
https://YOUR_RAILWAY_SERVICE.up.railway.app/api/stripe/webhook
```

Enable these Stripe events:

- `checkout.session.completed`
- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `invoice.payment_succeeded`
- `invoice.payment_failed`

## 5. LiveKit Call Tests

Before testing:

- Railway service is running.
- Railway logs show the worker registered as `outbound-caller`.
- `LIVEKIT_URL` starts with `wss://`.
- SIP trunk env is set.
- `SARVAM_API_KEY` is set for TTS.

Browser voice test:

1. Sign in to the dashboard.
2. Open Dashboard or Agent Setup.
3. Click the browser voice test.
4. Allow microphone/audio playback.
5. Watch Railway logs for:
   - `outbound-caller`
   - `Agent dispatch`
   - `Session live`
   - TTS provider log

Phone-call test:

1. Confirm `/api/livekit/health` and `/api/sip/health`.
2. Place an outbound/SIP test call from the dashboard.
3. Answer the phone.
4. Confirm greeting audio.
5. Watch Railway logs for:
   - `[ROOM] Connected`
   - `[SIP] Participant connected`
   - `[AGENT] Session live`
   - `[TTS] Using Sarvam Bulbul v3`

## 6. Multi-User SaaS Security

The dashboard requests call logs, contacts, and stats using the logged-in user's Supabase access token.

RLS allows:

- Legacy rows: `workspace_id` is null and `user_id = auth.uid()`
- Workspace rows: `workspace_id` is set and the user is a member of that workspace

On first authenticated API request, the backend ensures a Personal workspace and membership.

Production rules:

- Do not deploy without `SUPABASE_SERVICE_ROLE_KEY`.
- Do not put service role keys in frontend code.
- Do not commit `.env`.
- Use `env.railway.example` as the Railway variable checklist.

## 7. Before Push

Run:

```powershell
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run build
python -m compileall backend
```

Check:

- `.env` is ignored.
- `config.json` does not contain real API keys.
- Railway variables are configured from `env.railway.example`.
- Supabase migrations have been applied in production.

## 8. Quick MVP checklist (your deploy order)

1. **Vercel env** (Production — and Preview if you hit prod API):

   - `NEXT_PUBLIC_API_URL=https://YOUR_SERVICE.up.railway.app` (no trailing slash; must be HTTPS Railway hostname)
   - `NEXT_PUBLIC_SUPABASE_URL=https://YOUR_PROJECT.supabase.co` (full `https://` URL)
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY=...` (anon only; never service role)

2. **Railway env** (minimum):

   - `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`
   - `GROQ_API_KEY`, `SARVAM_API_KEY`
   - `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`
   - `CORS_ORIGIN=https://YOUR_VERCEL_APP.vercel.app`  
     For local dev alongside prod, append comma-separated origins, e.g. `http://localhost:3000,http://localhost:5173` (Railway defaults also allow `5173`; see [`backend/main.py`](backend/main.py) `_cors_origins`).
   - `PUBLIC_APP_URL=https://YOUR_VERCEL_APP.vercel.app` for redirects (Stripe/etc.)

3. **Supabase → Authentication → URL Configuration**

   - **Site URL**: `https://YOUR_VERCEL_APP.vercel.app`
   - **Redirect URLs**:  
     `https://YOUR_VERCEL_APP.vercel.app/**`  
     `https://YOUR_SERVICE.up.railway.app/**`  
     `http://localhost:3000/**`  
     `http://localhost:5173/**`  

   Email provider → **Confirm email**: **OFF** for MVP password signup without inbox step; turn **ON** before public launch.

4. **Redeploy**

   - Railway: redeploy after env changes (or redeploy triggers on git push).
   - Vercel: redeploy (_Clear build cache + Redeploy_ if assets or env behaved oddly).

5. **Smoke test**

   Signup → Login → Create agent → Publish agent → Start live call → confirm transcript/lead saved (`/logs`, CRM).
