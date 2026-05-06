# Vercel + Railway Deployment Guide

Use **Vercel only for the frontend** and **Railway for the backend/voice worker**.

## Why Railway Runs The Backend

The LiveKit voice worker must stay connected continuously. It waits for dispatch jobs, joins rooms, streams audio, and handles calls that can last several minutes.

Vercel serverless functions are not designed for that always-on worker process.

Railway runs the Docker container continuously, so it can host:

- FastAPI backend
- LiveKit worker
- SIP call handling
- Stripe webhooks
- Supabase-backed API routes

## Vercel Role

Vercel can host the React/Vite dashboard.

Set this Vercel environment variable:

```text
NEXT_PUBLIC_API_URL=https://YOUR_RAILWAY_SERVICE.up.railway.app
```

## Railway Role

Railway should deploy the project folder containing:

- `Dockerfile`
- `railway.toml`
- `supervisord.conf`
- `backend/`

Railway installs Python dependencies and starts both FastAPI and the LiveKit worker.
The React/Vite dashboard is deployed separately from `frontend/` on Vercel.

See `PRODUCTION_SETUP.md` for the full Railway setup checklist.
