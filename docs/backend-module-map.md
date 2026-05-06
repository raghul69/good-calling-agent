# Backend Module Map

## API Routers

| Module | Purpose | Key Endpoints |
|---|---|---|
| `auth` | Supabase auth bridge, session verification | `/api/auth/me`, `/api/auth/login`, `/api/auth/otp/*` |
| `orgs` | Organizations, workspaces, members, invites | `/api/orgs`, `/api/workspaces`, `/api/members` |
| `agents` | Agent CRUD, versioning, import/export/share | `/api/agents`, `/api/agents/{id}/versions`, `/api/agents/import` |
| `llm` | Provider settings, model catalog, fallback policies | `/api/providers/options`, `/api/provider-routes` |
| `audio` | STT/TTS settings, voices, voice clones | `/api/providers/audio`, `/api/voices` |
| `engine` | Runtime config, memory, tool orchestration | `/api/engine/config`, `/api/memory` |
| `calls` | Browser/outbound/inbound call APIs | `/api/calls/*` |
| `sip` | SIP trunks, numbers, inbound assignment | `/api/sip/*`, `/api/phone-numbers` |
| `tools` | CRM, Sheets, WhatsApp, Calendar, webhooks, APIs | `/api/tools`, `/api/tools/test` |
| `workflows` | Workflow builder and execution rules | `/api/workflows`, `/api/workflow-steps` |
| `campaigns` | CSV import, scheduling, dispatch, retries | `/api/campaigns`, `/api/campaign-runs` |
| `knowledge` | Uploads, chunking, embeddings, retrieval | `/api/knowledge-bases`, `/api/documents` |
| `analytics` | Call, campaign, cost, provider metrics | `/api/analytics/*` |
| `billing` | Razorpay plans, subscriptions, wallet, invoices | `/api/billing/*`, `/api/razorpay/webhook` |
| `admin` | System settings, tenants, audit logs, monitoring | `/api/admin/*` |
| `observability` | Health, readiness, logs, traces | `/api/health`, `/api/ops/readiness` |

## Services

### `AgentService`

- Creates agents and draft versions.
- Publishes immutable versions.
- Validates prompts, variables, provider config.
- Handles import/export and duplication.
- Current implementation stores agent versions in Supabase and passes resolved runtime config through LiveKit dispatch metadata.

### `ProviderRouter`

- Selects LLM/STT/TTS provider at runtime.
- Applies tenant budget, latency, region, and fallback policies.
- Emits usage events.

### `LiveKitOrchestrator`

- Creates rooms and tokens.
- Dispatches workers.
- Creates SIP participants.
- Assigns inbound numbers to agents.

### `CampaignScheduler`

- Parses CSV contacts.
- Validates E.164 phone numbers.
- Schedules calls by timezone, quiet hours, and tenant quotas.
- Enqueues call jobs.

### `WorkflowEngine`

- Runs workflow steps.
- Evaluates conditions:
  - answered
  - no answer
  - sentiment
  - qualified lead
  - booking created
  - webhook response
- Advances campaign contacts.

### `ToolExecutionService`

- Executes external actions from voice calls.
- Applies allowlists, schema validation, timeout, retries.
- Redacts secrets in logs.

### `KnowledgeService`

- Stores source files.
- Extracts text.
- Chunks and embeds.
- Returns relevant snippets per agent and call context.

### `BillingService`

- Owns Razorpay subscriptions.
- Tracks credits and usage.
- Generates invoice rows.
- Enforces quotas before call dispatch.

## Worker Jobs

| Job | Queue | Purpose |
|---|---|---|
| `campaign.import_csv` | `campaigns` | Parse and validate uploaded contacts |
| `campaign.dispatch_contact` | `calls` | Start next eligible call |
| `call.retry_due` | `calls` | Retry failed/no-answer calls |
| `workflow.advance` | `workflows` | Move contact to next step |
| `knowledge.ingest_document` | `knowledge` | Chunk/embed uploaded file |
| `analytics.aggregate_hourly` | `analytics` | Build rollups |
| `billing.rate_usage` | `billing` | Convert usage events to billable records |

## Runtime Contracts

All service calls must carry:

- `request_id`
- `organization_id`
- `workspace_id`
- `user_id` when user-initiated
- `agent_version_id` when call-related
- `call_id` when call-related
