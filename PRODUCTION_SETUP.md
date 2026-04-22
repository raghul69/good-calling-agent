# Production Setup

## 1. Supabase

Run `supabase_migration_v2.sql` in the Supabase SQL Editor, then run **`supabase_migration_saas_workspaces.sql`** for multi-tenant workspaces (`workspaces`, `workspace_members`, `workspace_settings`, `workspace_id` on call data, and RLS).

Auth settings:

- Authentication -> URL Configuration -> Site URL (use your real public API/dashboard origin):
  - **Render:** `https://YOUR_RENDER_SERVICE.onrender.com`
  - **Railway:** `https://YOUR_RAILWAY_SERVICE.up.railway.app` (or your custom domain)
- Authentication -> URL Configuration -> Redirect URLs (add every origin you use):
  - `https://YOUR_RENDER_SERVICE.onrender.com/**` (if using Render)
  - `https://YOUR_RAILWAY_SERVICE.up.railway.app/**` (if using Railway)
  - `http://127.0.0.1:8001/**`
  - `http://localhost:8001/**`
- Authentication -> Providers -> Email:
  - Enable Email provider.
  - Enable Confirm email if you want password signup to require email verification.
  - Enable OTP / Magic Link email flow.

Email templates:

- Keep the OTP template short.
- If you later add redirect links, use `{{ .RedirectTo }}` instead of only `{{ .SiteURL }}`.

Keys needed for Render or Railway:

- `SUPABASE_URL`
- `SUPABASE_KEY` - anon public key
- `SUPABASE_ANON_KEY` - optional alias for the same anon public key
- `SUPABASE_SERVICE_ROLE_KEY` - server only, never expose in frontend
- `SUPABASE_S3_ACCESS_KEY`
- `SUPABASE_S3_SECRET_KEY`
- `SUPABASE_S3_ENDPOINT`
- `SUPABASE_S3_REGION`

## 2. Render

Deploy from `render.yaml`.

Required environment variables:

- `SUPABASE_URL`
- `SUPABASE_KEY`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_S3_ACCESS_KEY`
- `SUPABASE_S3_SECRET_KEY`
- `SUPABASE_S3_ENDPOINT`
- `SUPABASE_S3_REGION`
- `LIVEKIT_URL`
- `LIVEKIT_API_KEY`
- `LIVEKIT_API_SECRET`
- `OPENAI_API_KEY`
- `SARVAM_API_KEY`
- `CAL_API_KEY`
- `CAL_EVENT_TYPE_ID`

Health check:

- Path: `/api/health`

After deploy, open:

```text
https://YOUR_RENDER_SERVICE.onrender.com/api/health
```

## 2b. Railway (alternative to Render)

Use the **same** environment variables as in the Render list above. In the Railway service, set each variable under **Variables** (or link to a shared variable set). Set **Start Command** / root to match how you run the app (e.g. Uvicorn on the port Railway provides via `PORT`).

Health check:

```text
https://YOUR_RAILWAY_SERVICE.up.railway.app/api/health
```

(Replace with your Railway public URL or custom domain.)

The response should show:

- `supabase.configured: true`
- `supabase.service_role_key_present: true`
- `livekit.configured: true`
- `livekit.url_valid: true`

If the login form shows `Supabase not configured`, the backend is missing `SUPABASE_URL` plus either `SUPABASE_KEY` or `SUPABASE_ANON_KEY`. Restart the service after adding the variables.

## 2c. GitHub → Railway (direct deploy, InboundAIVoice)

This app ships as a **single Docker image**: [Dockerfile](Dockerfile) builds the Vite frontend, installs Python deps, and runs [supervisord.conf](supervisord.conf) (FastAPI + LiveKit agent). [railway.toml](railway.toml) pins **Dockerfile** build and **`/api/health`**. [.dockerignore](.dockerignore) keeps the build context small.

### Repo layout (choose one)

1. **Recommended:** A GitHub repository whose **repository root is the InboundAIVoice folder** (same files as this project: `Dockerfile`, `backend/`, `frontend/`, etc.). Connect that repo to Railway with **no** custom root directory.
2. **Monorepo / submodule:** If the Git root is **above** InboundAIVoice (e.g. parent folder + git submodule), in Railway open the service → **Settings → Root Directory** and set **`InboundAIVoice`** (or the path that contains `Dockerfile`). Ensure the submodule is **committed** and that `git clone --recurse-submodules` would populate code, or Railway’s build will see an empty tree.

### Connect GitHub and deploy

1. [Railway Dashboard](https://railway.app) → **New Project** → **Deploy from GitHub repo** → authorize the org/user → select the repo and branch (e.g. `main`).
2. If using a monorepo, set **Root Directory** to **`InboundAIVoice`** as above.
3. Railway should detect **Dockerfile** (see [railway.toml](railway.toml)). Do **not** override the start command unless you know you need to; the image **CMD** runs supervisord.
4. **Variables:** Add every name from **§2 Render** (or copy from [env.railway.example](env.railway.example)). Mark values as **secrets**.
5. **Networking:** **Generate Domain** (or attach a custom domain). Note the public URL `https://…up.railway.app`.
6. **Health check:** With [railway.toml](railway.toml), Railway probes **`/api/health`** during deploy; ensure the service returns **HTTP 200** once Uvicorn is up.
7. Push to the connected branch → Railway **redeploys automatically**.

### After the first successful deploy

1. Open `https://YOUR_SERVICE.up.railway.app/api/health` and confirm flags in §2b.
2. Complete **§1 Supabase Auth** URL configuration using that **exact** public origin (Site URL + Redirect URLs).
3. Smoke-test login, demo call, and outbound call per **§3**.

## 2d. Cursor MCP for Supabase

Cursor MCP config lives at `C:\Users\raghu\.cursor\mcp.json`. This repo expects the official hosted Supabase MCP server:

```json
{
  "mcpServers": {
    "supabase": {
      "url": "https://mcp.supabase.com/mcp?read_only=true",
      "headers": {}
    }
  }
}
```

After editing MCP config, restart Cursor, open **Settings -> Cursor Settings -> Tools & MCP**, and sign in to Supabase when prompted. The MCP connection helps inspect Supabase tables and settings, but the running app still needs `SUPABASE_URL`, `SUPABASE_KEY` or `SUPABASE_ANON_KEY`, and `SUPABASE_SERVICE_ROLE_KEY` in its backend environment.

## 3. LiveKit Demo Call Test

Before testing:

- Make sure the Render or Railway service is running.
- Make sure the agent process starts without errors in Render logs.
- Make sure `LIVEKIT_URL` starts with `wss://`.
- Make sure the worker agent name is `outbound-caller`.

Test flow:

1. Sign in to the dashboard.
2. Open `/api/livekit/test` in the same browser session.
3. Confirm it returns `success: true`.
4. Go to Dashboard.
5. Click `Start Live Call`.
6. Allow microphone/audio playback in the browser.
7. Watch Render or Railway logs for:
   - `Uvicorn running`
   - `outbound-caller`
   - `Agent dispatch`
   - `Session live`
8. Watch LiveKit Cloud for the demo room.
9. Speak into the browser and confirm the voice agent responds.

If the demo token endpoint returns DNS errors, check `LIVEKIT_URL`.
If dispatch fails, check that the agent worker is running and its agent name is `outbound-caller`.

## 4. Multi-User SaaS Security

The dashboard requests call logs, contacts, and stats using the logged-in user's Supabase access token. RLS allows:

- **Legacy rows:** `workspace_id` is null and `user_id = auth.uid()`
- **Workspace rows:** `workspace_id` is set and the user is a member of that workspace (see `supabase_migration_saas_workspaces.sql`)

On first authenticated API request, the backend ensures a **Personal** workspace and membership (`ensure_default_workspace`). LiveKit dispatch and demo tokens include `workspace_id` in metadata so the agent can attribute calls and recordings to the tenant.

The agent writes call logs with `SUPABASE_SERVICE_ROLE_KEY` and stores `user_id` and `workspace_id` from LiveKit dispatch metadata.

Required production rule:

- Do not deploy without `SUPABASE_SERVICE_ROLE_KEY`.
- Do not put service role keys in frontend code.
- Do not commit `.env`.

## 5. Before Push

Run:

```powershell
npm.cmd run build
npm.cmd test
.\venv\Scripts\python.exe -m compileall backend
```

Check:

- `.env` is ignored.
- `config.json` does not contain real API keys.
- `.cursor/mcp.json` does not contain hardcoded Render tokens.
- `render.yaml` uses `sync: false` for secrets.
- `supabase_migration_v2.sql` has owner-based RLS, not allow-all policies.
- Railway: use [env.railway.example](env.railway.example) as a variable checklist; never commit filled-in secrets.
