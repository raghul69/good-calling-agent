# SaaS Roadmap

## Phase 0: Stabilize Current App

Goal: ship a reliable Railway/Vercel version of the existing app.

- Commit and push current Railway-only deploy work.
- Configure Railway variables.
- Configure Vercel `NEXT_PUBLIC_API_URL`.
- Apply Supabase migrations.
- Verify health endpoints.
- Run browser call, outbound call, inbound call proof.
- Enable Sentry.

Exit criteria:

- One real user can log in, create/use an agent, place a call, and see logs.

## Phase 1: Agent Builder v1

- Status: backend/data foundation implemented first; full visual builder remains on the current Vite shell until the later Next.js/shadcn migration.
- Agent foundation shipped: versioned persistence, protected APIs, runtime dispatch metadata, provider usage logging, audit logs, and `supabase_migration_agent_foundation.sql`.
- DB-backed agents must have a published version before calls use saved config.
- Agent CRUD.
- Draft/published versions.
- Welcome message and system prompt.
- Tamil, Tamil/Tanglish, Hindi, English, and multilingual presets.
- Voice selection.
- LLM provider and model selection: OpenAI, Groq, Claude, Gemini.
- TTS provider selection: Sarvam AI and ElevenLabs.
- Import/export JSON.
- Duplicate agent.
- Runtime metadata carries `agent_id`, `agent_version_id`, and resolved provider config into the LiveKit worker.

Exit criteria:

- Calls use immutable published agent versions.

## Phase 2: Calling and SIP

- SIP trunk CRUD.
- Phone number inventory.
- Inbound number assignment.
- Browser calling.
- Outbound test call.
- Warm transfer.
- Call states/events.
- Retry policy UI.

Exit criteria:

- Inbound and outbound both proven in production logs.

## Phase 3: Tools and Workflows

- Tool registry.
- Calendar booking.
- Webhook action.
- Google Sheets append.
- WhatsApp message action.
- Workflow builder with call, delay, WhatsApp, webhook steps.
- Conditional transitions.

Exit criteria:

- A workflow can qualify a lead, book a meeting, and send a follow-up.

## Phase 4: Campaigns

- CSV upload.
- Contact validation.
- Campaign scheduler.
- Quiet hours/timezone.
- Retry campaigns.
- Campaign analytics.
- Pause/resume/cancel.

Exit criteria:

- 1,000-contact campaign can run safely with rate limits.

## Phase 5: Knowledge Base

- PDF/doc upload.
- Text extraction.
- Chunking.
- Embeddings.
- Vector search.
- Agent-specific KB assignment.
- RAG citations in debug logs.

Exit criteria:

- Agent answers from tenant KB without cross-tenant leakage.

## Phase 6: Billing

Primary provider: Razorpay.

- Plans.
- Subscriptions.
- Usage wallet.
- Included minutes.
- Overage billing.
- Invoices.
- Quota enforcement.

Exit criteria:

- Calls stop or require top-up when quota/wallet is exhausted.

## Phase 7: Enterprise Admin

- Organizations.
- Workspace invites.
- RBAC management.
- Audit logs.
- System monitoring.
- Provider-level cost dashboard.
- Dedicated tenant controls.

Exit criteria:

- Admin can manage users, roles, usage, billing, and incidents.

## Phase 8: Scale and Reliability

- Redis queues.
- Separate API, voice, campaign, analytics workers.
- Load testing.
- Multi-worker LiveKit dispatch.
- Provider circuit breakers.
- Multi-region worker strategy.

Exit criteria:

- 250+ concurrent calls with stable latency and controlled provider cost.
