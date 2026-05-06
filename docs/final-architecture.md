# Final Architecture

## Product Goal

Build a multi-tenant AI voice calling SaaS for creating, deploying, testing, and scaling realtime voice agents. The platform is inspired by mature voice-agent dashboards with tabbed agent configuration, workflows, campaigns, call logs, integrations, and operational controls, but is designed as an original enterprise-grade system.

Primary capabilities:

- Realtime outbound, inbound, and browser calls.
- Agent setup with prompts, multilingual settings, voice/LLM/audio controls, tools, analytics, and inbound assignment.
- Campaigns that execute workflows across CSV/contact lists with retries and conditional transitions.
- Multi-provider LLM, TTS, and STT routing with fallback and cost tracking.
- Tenant isolation, RBAC, billing, audit logs, observability, and production QA controls.

## High-Level System

```text
Vercel Frontend
  Next.js, Tailwind, shadcn/ui
  Dashboard, agent builder, campaigns, billing, admin
        |
        v
Railway API Gateway
  FastAPI REST + webhooks
  Auth, tenancy, billing, config, campaigns, analytics
        |
        +--> Supabase/Postgres
        |    Tenants, agents, calls, workflows, usage, billing, audit logs
        |
        +--> Redis Queue
        |    Campaign jobs, retries, ingestion, post-call processing
        |
        +--> Worker Services
        |    LiveKit agent workers, campaign workers, analytics workers
        |
        +--> LiveKit Cloud
        |    Realtime rooms, SIP participants, browser calls
        |
        +--> Providers
             OpenAI, Groq, Claude, Gemini, Sarvam, ElevenLabs, Telnyx/Vobiz,
             Razorpay, WhatsApp, Google Sheets, Calendar, webhooks
```

## Service Boundaries

### Frontend App

- Framework: Next.js App Router.
- UI: Tailwind + shadcn/ui.
- Auth: Supabase session in browser, API calls with Bearer token.
- Pages:
  - Agent setup
  - LLM configuration
  - Audio configuration
  - Engine/orchestrator settings
  - Calls and SIP trunks
  - Tools
  - Knowledge base
  - Workflows
  - Campaigns
  - Analytics
  - Billing
  - Admin
  - Observability/support

### API Service

- Framework: FastAPI.
- Responsibilities:
  - Request auth and tenant context.
  - CRUD APIs for agents, tools, workflows, campaigns, trunks, knowledge bases.
  - LiveKit room/token/dispatch APIs.
  - Billing and Razorpay webhooks.
  - Admin, audit, usage, and analytics APIs.
  - Provider registry and feature flags.

### Voice Worker

- Runtime: Python worker process on Railway or separate worker service.
- Responsibilities:
  - Register LiveKit agent.
  - Join dispatched rooms.
  - Configure STT, LLM, TTS dynamically from agent version.
  - Execute tool calls.
  - Stream transcripts and events.
  - Persist call completion artifacts.

### Campaign Worker

- Runtime: Celery or BullMQ worker.
- Responsibilities:
  - Import CSV contacts.
  - Schedule calls by timezone and quiet hours.
  - Dispatch call jobs.
  - Apply retry policy.
  - Advance workflow steps based on outcomes.

### Analytics Worker

- Runtime: Celery/BullMQ scheduled jobs.
- Responsibilities:
  - Aggregate daily/hourly metrics.
  - Calculate provider costs.
  - Run sentiment and disposition extraction.
  - Build campaign and agent rollups.

## Realtime Call Lifecycle

1. User starts a browser, outbound, inbound, or campaign call.
2. API creates or resolves a LiveKit room.
3. API dispatches the selected agent worker with metadata:
   - `tenant_id`
   - `workspace_id`
   - `agent_version_id`
   - `call_id`
   - `campaign_contact_id`
   - `first_line`
4. Worker loads immutable agent version config.
5. Worker starts LiveKit `AgentSession`.
6. Worker selects provider routes for STT, LLM, and TTS.
7. Worker speaks welcome message after answer/session start.
8. Worker streams transcripts and call events.
9. Tools execute through the API action layer.
10. Shutdown hook saves transcript, recording, summary, sentiment, usage, cost, and workflow outcome.
11. Campaign worker advances the next step if this call belongs to a campaign.

## Agent Builder Model

Agent setup is versioned. Editing an agent creates a draft version; publishing freezes the version used by calls.

Tabs:

- Agent: name, welcome message, system prompt, language, variables, sharing.
- LLM: provider, model, temperature, fallback, max tokens, provider routing.
- Audio: STT, TTS, voice, language, noise suppression, voice clone.
- Engine: LiveKit settings, memory, tool calling, workflow hooks.
- Call: inbound/outbound config, SIP trunk, caller ID, retry policy.
- Tools: CRM, Sheets, WhatsApp, Calendar, webhooks, external actions.
- Analytics: extraction schema, sentiment, dispositions, success criteria.
- Inbound: phone number assignment, business hours, fallback/handoff.

## Provider Routing

Provider routing is policy-driven:

- Default route per agent.
- Fallback provider per layer.
- Budget caps per tenant and campaign.
- Latency threshold fallback.
- Region/data residency constraints.
- Provider failure circuit breaker.

Example:

```json
{
  "llm": {
    "primary": "groq:llama-3.3-70b-versatile",
    "fallback": ["openai:gpt-4o-mini", "claude:haiku"],
    "temperature": 0.3,
    "max_tokens": 96
  },
  "tts": {
    "primary": "sarvam:bulbul-v3:kavya",
    "fallback": ["elevenlabs:turbo-v2.5"]
  },
  "stt": {
    "primary": "sarvam:auto",
    "fallback": ["deepgram:nova-3"]
  }
}
```

## Tenancy

- Every business account is an organization.
- Each organization has workspaces.
- Users are members of workspaces with roles.
- All operational rows carry `organization_id` and `workspace_id`.
- RLS protects tenant reads.
- Service role writes are used only by trusted backend/worker services.

## Billing

Requested billing provider: Razorpay.

Billing model:

- Subscription plan.
- Included minutes.
- Usage overage by AI minute and telephony minute.
- Credit wallet for prepaid usage.
- Invoice generation.
- Usage events collected per call and provider.

Stripe can remain as an optional international billing adapter, but Razorpay should be the primary India billing provider.

## Source Inspiration

Bolna public docs show a tabbed agent setup model, workflows, campaigns, CSV campaign creation, workflow-agent pairs, inbound agents, knowledge bases, call logs, and multilingual voice agents. This architecture borrows those product categories, not proprietary UI/code.

Sources:

- https://www.bolna.ai/docs/agent-setup/overview
- https://www.bolna.ai/docs/workflows-and-campaigns
- https://www.bolna.ai/docs/introduction
