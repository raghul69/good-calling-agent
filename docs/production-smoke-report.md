# Production smoke verification report

_Last updated by repo tooling: fill operational results below after you run QA in your deployed environment._

## URLs

| Resource | URL / value |
|----------|--------------|
| **Production demo app (canonical)** | _(e.g. your Vercel URL)_ |
| **Railway backend / worker services** | _(service names/links)_ |
| **Supabase project** | _(optional)_ |

## Repo / config changes shipped

- **`DEFAULT_TRANSFER_NUMBER`** documented in [env.railway.example](../env.railway.example). Set in Railway for fleet fallback, or rely on **Call tab → Transfer destination (E.164)** per agent (`call_config.transfer_destination_e164`).
- **Tools tab:** Custom function labeled **Coming soon**, **UI-only; no backend tool yet** ([App.tsx](../frontend/src/App.tsx)).

## 1. Persistence (Engine / Call / Tools / Analytics / Inbound)

| Step | Pass / Fail | Notes |
|------|-------------|-------|
| Edited distinct value on Engine tab | | |
| Edited distinct value on Call tab (incl. E.164 if using transfer) | | |
| Toggled Tools (non-custom) | | |
| Changed Analytics toggles | | |
| Changed Inbound fields | | |
| Saved agent | | |
| Hard refresh | | |
| All values restored in UI | | |
| Published agent | | |

## 2. Runtime call & Railway logs

| Check | Pass / Fail | Notes |
|-------|-------------|-------|
| Browser **or** inbound production call completed | | |
| `[AGENT_CONFIG]` in worker logs | | |
| `[ENGINE_CONFIG]` | | |
| `[CALL_CONFIG]` | | |
| `[TOOLS_CONFIG]` | | |
| `[AUDIO_CONFIG]` | | |
| `[ANALYTICS_CONFIG]` (optional corroboration) | | |
| `[AGENT] Session live` | | |
| `[LLM] Using Groq` (or other provider if configured) | | |
| `[TTS] Using Sarvam` or `[TTS] Using ElevenLabs` | | |
| AI audio heard | | |
| Logs reflect **saved** engine/call values (spot-check JSON snippet) | | |

## 3. `/api/logs` (authenticated)

| Check | Pass / Fail | Notes |
|-------|-------------|-------|
| `GET /api/logs` (or UI list backed by it) shows new row after test call | | |
| Row fields look sane (status, duration, agent linkage, etc.) | | |

## 4. Transfer tool

| Scenario | Pass / Fail | Notes |
|----------|-------------|-------|
| **Save:** Transfer enabled + invalid/missing E.164 → save blocked with clear message | | |
| **Runtime:** Transfer enabled + no `transfer_destination_e164` and no `DEFAULT_TRANSFER_NUMBER` → log `transfer_call enabled but no transfer destination — removing tool` | | |
| **Optional:** Valid E.164 + transfer enabled → tool present; live transfer only if you intentionally dial out | | |

## Summary

| Area | Status |
|------|--------|
| **Persistence** | |
| **Runtime config alignment** | |
| **Browser / inbound call** | |
| **Transfer validation** | |

## Blockers

_List any unresolved issues (SIP trunk, env vars, RLS on `call_logs`, CORS, etc.)._

---

_To run automated checks locally (no prod):_

```powershell
Set-Location InboundAIVoice/frontend; npm run build
Set-Location ..; python -m pytest backend/tests/test_main.py -q
```
