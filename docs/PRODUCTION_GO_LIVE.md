# Production go-live — good-calling-agent (MVP hardening)

Operational runbook for releasing the current stack: **Vercel** (React/Vite UI) + **Railway** (FastAPI + LiveKit worker via supervisord) + **Supabase** (auth + Postgres).

This is **not** a multi-tenant SaaS or billing launch checklist.

---

## Final env checklist

### Railway (API + worker)

Verify in **Railway → Service → Variables** (production). Values must be non-empty where required.

| Variable | Notes |
|----------|--------|
| `LIVEKIT_URL` | HTTPS WebSocket host for LiveKit Cloud (no trailing path noise). |
| `LIVEKIT_API_KEY` | Server API key. |
| `LIVEKIT_API_SECRET` | Server API secret. |
| `LIVEKIT_SIP_TRUNK_ID` **or** `OUTBOUND_TRUNK_ID` | SIP outbound trunk LiveKit ID (either name accepted by the app). |
| `SARVAM_API_KEY` | Required when STT/TTS provider is Sarvam. |
| `GROQ_API_KEY` **or** `OPENAI_API_KEY` | At least one must be set for LLM-backed voice/agent paths. `/health` exposes `mvp_env.required.GROQ_OR_OPENAI_API_KEY`. |
| `SUPABASE_URL` | Project URL. |
| `SUPABASE_ANON_KEY` | Public anon key (server health + client-style checks). |
| `SUPABASE_SERVICE_ROLE_KEY` | Service role for inserts/RLS bypass where the backend uses it. **Keep secret.** |
| `CORS_ORIGIN` | Comma-separated allowed **browser** origins (exact `https://your-app.vercel.app`, no trailing slash). Include dev origins only if you intentionally hit prod API from localhost. |
| `DEFAULT_TRANSFER_NUMBER` | Required for MVP env gate in `/health` (transfer behavior). |

Strongly recommended / already used in repo:

- `PUBLIC_APP_URL` — canonical UI URL for redirects and ops docs.
- Optional: `CORS_ORIGIN_REGEX` — set to `disabled` to turn off preview-host regex if you do not want it.

See also: [`PRODUCTION_SETUP.md`](../PRODUCTION_SETUP.md), [`docs/VERCEL_PRODUCTION_CHECKLIST.md`](VERCEL_PRODUCTION_CHECKLIST.md).

### Vercel (frontend)

| Variable | Notes |
|----------|--------|
| `NEXT_PUBLIC_API_URL` | Railway API base URL, **no trailing slash**. |
| `NEXT_PUBLIC_SUPABASE_URL` | Same project as Railway `SUPABASE_*`. |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon (public) key for browser auth. |

### Supabase Dashboard

- **Authentication → URL configuration**: Site URL = production Vercel origin; redirect allowlist includes production, preview (if used), and local dev patterns as needed.
- **RLS / policies**: Confirm `call_logs`, agents, and workspace-scoped tables match your migration set (see `PRODUCTION_SETUP.md`).

---

## Automated checks (run before tagging a release)

From repo root **`InboundAIVoice`** (or adjust paths).

### Frontend

```powershell
cd frontend
npm ci
npm run build
npm test -- --run
```

### Backend

```powershell
cd ..
$env:PYTHONPATH = "."
python -m pytest backend/tests -q
```

### Deployed API (optional but recommended)

Requires network access to Railway:

```powershell
$env:PUBLIC_API_URL = "https://YOUR-SERVICE.up.railway.app"
python scripts/check_deployed_health.py
```

The script calls `GET {PUBLIC_API_URL}/health` and exits **0** only when `mvp_env_ready` is true **and** `missing` is empty. If `PUBLIC_API_URL` is unset, the script exits **0** and prints a skip message (CI-friendly).

---

## Manual smoke test checklist (production)

Run against **production** Vercel + Railway URLs. Use a **dedicated test identity** and **test phone**.

- [ ] Signup / login (Supabase session present; no redirect loop).
- [ ] **Agents**: create agent, set Tamil RE (or your standard RE template), save, **publish** a version.
- [ ] Place **test outbound / SIP call** from the UI as you do today.
- [ ] Phone **rings**, callee answers.
- [ ] Agent **speaks** (TTS/STT path OK).
- [ ] Call **ends** cleanly (no hung room; worker logs quiet after shutdown).
- [ ] **CRM / contacts**: row or rollup appears as designed (if enabled for workspace).
- [ ] **`/logs`**: new row appears; **transcript** and **summary** present when backend saved them.
- [ ] **`orch_lead`** visible in summary / CRM tokens (parsed `orch_lead=` segment).
- [ ] Worker/API logs contain expected markers (e.g. **`[CALL_END]`**, **`[CRM]`**) for the session — use Railway log timeline for that correlation.

Record pass/fail and the UTC timestamp of the test call for rollback forensics.

---

## Rollback steps

1. **Vercel**: in the project **Deployments** list, **Promote** the last known-good deployment to production (or revert the Git commit that introduced the regression and let CI deploy).
2. **Railway**: **Deployments →** redeploy previous **successful** image, or revert env var changes and trigger redeploy.
3. **Supabase**: avoid destructive migrations on go-live day; if a bad migration shipped, restore from backup / run down migration only if you have a tested procedure.
4. **DNS / custom domain**: if you moved domains, revert DNS at the registrar only after traffic is stable.

---

## Known limitations (MVP)

- **Pagination / export**: call history is server-paginated; CSV export is **current page** only unless you add a chunked export later.
- **Health vs runtime**: `/health` validates env presence, not end-to-end voice quality or carrier SLAs.
- **Provider keys**: Sarvam/Groq/OpenAI must match the **actual** model/provider selected on the agent; missing provider key fails at runtime even if another LLM key exists.
- **SIP / PSTN**: trunk misconfiguration, provider errors, or regional blocking are outside app code; use LiveKit + carrier dashboards.
- **Cost / abuse**: rate limits and billing are out of scope for this MVP doc; monitor usage in provider consoles.

---

## Compliance & safety reminders

- **Recording & consent**: ensure your welcome script and jurisdiction-specific rules cover **recording**, **AI disclosure**, and **telemarketing** obligations (TCPA/GDPR/local rules as applicable).
- **PII**: transcripts and CRM fields may contain phone numbers and names — restrict Railway/Vercel/Supabase access, enable audit where required, define retention.
- **Secrets**: never commit `.env`; rotate keys if leaked; restrict Supabase **service role** to server-only.

---

## Exact go-live order (recommended)

1. Freeze `main`; run **frontend build + tests** and **backend tests** locally or in CI.
2. Set **Railway** env (table above); redeploy; wait for green Railway healthcheck (`GET /health`).
3. Set **Vercel** env; redeploy frontend.
4. Run `python scripts/check_deployed_health.py` with **`PUBLIC_API_URL`**.
5. Run **manual smoke test** (section above).
6. Monitor **Railway logs** and **Supabase** for errors for ~30–60 minutes after first production traffic.

---

## References

- [`PRODUCTION_SETUP.md`](../PRODUCTION_SETUP.md)
- [`docs/VERCEL_PRODUCTION_CHECKLIST.md`](VERCEL_PRODUCTION_CHECKLIST.md)
- [`scripts/check_deployed_health.py`](../scripts/check_deployed_health.py)
