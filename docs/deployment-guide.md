# Deployment Guide

## Production Topology

- Frontend: Vercel.
- Backend API: Railway Docker service.
- Voice workers: Railway worker services or the same Docker image under `supervisord` for MVP.
- Queue: Redis.
- Database: Supabase/Postgres.
- Storage: Supabase Storage or S3-compatible bucket.
- Realtime voice: LiveKit Cloud.
- Billing: Razorpay primary, Stripe optional/international.

## Environments

| Environment | Purpose |
|---|---|
| `local` | Developer machine |
| `staging` | QA with test keys and sandbox billing |
| `production` | Real users, real calls, real billing |

## Railway Backend

Railway service root must include:

- `Dockerfile`
- `railway.toml`
- `supervisord.conf`
- `backend/`
- `frontend/`
- `requirements.txt`

Required Railway variables:

```text
SUPABASE_URL=
SUPABASE_KEY=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_S3_ACCESS_KEY=
SUPABASE_S3_SECRET_KEY=
SUPABASE_S3_ENDPOINT=
SUPABASE_S3_REGION=

LIVEKIT_URL=
LIVEKIT_API_KEY=
LIVEKIT_API_SECRET=
LIVEKIT_SIP_TRUNK_ID=
OUTBOUND_TRUNK_ID=

OPENAI_API_KEY=
GROQ_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
SARVAM_API_KEY=
ELEVENLABS_API_KEY=

CORS_ORIGIN=
PUBLIC_APP_URL=
SENTRY_DSN=

RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=
RAZORPAY_WEBHOOK_SECRET=

REDIS_URL=
```

Health checks:

```text
/health
/api/health
/api/livekit/health
/api/sip/health
/api/ops/readiness
```

## Vercel Frontend

Configure in the Vercel dashboard (`frontend/` root):

- **`frontend/vercel.json`** — Vite preset, output `dist` (SPA rewrites optional at project level).

Required Vercel variables:

```text
NEXT_PUBLIC_API_URL=https://YOUR_RAILWAY_SERVICE.up.railway.app
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
```

Build settings:

- Framework: Next.js after migration.
- Current Vite app:
  - Root: `frontend`
  - Build: `npm install && npm run build`
  - Output: `dist`

## Supabase

Apply migrations in order:

1. `supabase_migration_v2.sql`
2. `supabase_migration_saas_workspaces.sql`
3. `supabase_migration_production_hardening.sql`
4. `supabase_migration_agent_foundation.sql`

The agent foundation migration adds workspace-scoped agents, immutable agent versions, provider routes, provider usage events, audit logs, and `call_logs.agent_version_id`.

Auth URLs:

```text
Site URL:
https://YOUR_RAILWAY_SERVICE.up.railway.app

Redirect URLs:
https://YOUR_RAILWAY_SERVICE.up.railway.app/**
https://YOUR_VERCEL_FRONTEND.vercel.app/**
```

## LiveKit

Configure:

- Cloud project.
- API key and secret.
- SIP trunk.
- Inbound dispatch rules.
- Egress recording storage.

Worker name:

```text
outbound-caller
```

Future names:

```text
voice-agent-default
voice-agent-enterprise
voice-agent-high-concurrency
```

## Razorpay

Configure:

- Plan products.
- Subscription plans.
- Webhook endpoint:

```text
https://YOUR_RAILWAY_SERVICE.up.railway.app/api/razorpay/webhook
```

Events:

- `subscription.activated`
- `subscription.charged`
- `subscription.completed`
- `subscription.cancelled`
- `payment.failed`
- `invoice.paid`

## Deployment Gates

Do not mark production ready until:

- Backend health returns `ok`.
- LiveKit health reaches API.
- SIP health is true.
- Supabase service role present.
- Vercel frontend points to Railway API.
- One browser call succeeds.
- One outbound SIP call succeeds.
- One inbound call succeeds.
- Billing sandbox checkout and webhook succeed.
- Sentry receives a test event.
