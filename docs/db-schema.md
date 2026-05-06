# DB Schema

Database: Supabase/Postgres.

Every tenant-scoped table includes:

- `organization_id uuid not null`
- `workspace_id uuid not null`
- `created_at timestamptz not null default now()`
- `updated_at timestamptz not null default now()`

## Identity and Tenancy

```sql
organizations (
  id uuid primary key,
  name text not null,
  slug text unique,
  status text not null default 'active',
  created_by uuid references auth.users(id)
);

workspaces (
  id uuid primary key,
  organization_id uuid references organizations(id),
  name text not null,
  created_by uuid references auth.users(id)
);

workspace_members (
  workspace_id uuid references workspaces(id),
  user_id uuid references auth.users(id),
  role text check (role in ('owner','admin','developer','analyst','agent_manager','billing','member')),
  primary key (workspace_id, user_id)
);

invitations (
  id uuid primary key,
  workspace_id uuid references workspaces(id),
  email text not null,
  role text not null,
  token_hash text not null,
  expires_at timestamptz not null,
  accepted_at timestamptz
);
```

## Agents

```sql
agents (
  id uuid primary key,
  organization_id uuid not null,
  workspace_id uuid not null,
  name text not null,
  description text,
  status text not null default 'draft',
  visibility text not null default 'private',
  default_language text default 'multilingual',
  active_version_id uuid references agent_versions(id),
  created_by uuid references auth.users(id),
  deleted_at timestamptz
);

agent_versions (
  id uuid primary key,
  agent_id uuid references agents(id),
  version integer not null,
  status text check (status in ('draft','published','archived')),
  welcome_message text,
  system_prompt text,
  multilingual_prompts jsonb default '{}'::jsonb,
  prompt_variables jsonb default '[]'::jsonb,
  llm_config jsonb not null,
  audio_config jsonb not null,
  engine_config jsonb not null,
  call_config jsonb not null,
  tools_config jsonb default '[]'::jsonb,
  analytics_config jsonb default '{}'::jsonb,
  published_at timestamptz,
  unique (agent_id, version)
);

agent_shares (
  id uuid primary key,
  agent_id uuid references agents(id),
  shared_with_workspace_id uuid references workspaces(id),
  permission text check (permission in ('view','clone','edit'))
);
```

Current migration file: `supabase_migration_agent_foundation.sql`.

## Providers

```sql
provider_accounts (
  id uuid primary key,
  workspace_id uuid references workspaces(id),
  provider_type text check (provider_type in ('llm','stt','tts','telephony','messaging')),
  provider_name text not null,
  encrypted_credentials jsonb not null,
  status text default 'active'
);

provider_routes (
  id uuid primary key,
  workspace_id uuid references workspaces(id),
  name text not null,
  route_type text check (route_type in ('llm','stt','tts')),
  primary_provider text not null,
  fallback_providers jsonb default '[]'::jsonb,
  cost_limit_usd numeric,
  latency_limit_ms integer
);

provider_usage_events (
  id bigint primary key,
  workspace_id uuid references workspaces(id),
  user_id uuid references auth.users(id),
  agent_id uuid references agents(id),
  agent_version_id uuid references agent_versions(id),
  call_log_id bigint references call_logs(id),
  provider_type text,
  provider_name text,
  model text,
  metric text not null,
  quantity numeric default 0,
  estimated_cost_usd numeric default 0,
  metadata jsonb default '{}'::jsonb
);
```

## Calls

```sql
phone_numbers (
  id uuid primary key,
  workspace_id uuid references workspaces(id),
  provider text not null,
  phone_number text not null,
  country text,
  capabilities jsonb,
  assigned_agent_id uuid references agents(id),
  status text default 'active'
);

sip_trunks (
  id uuid primary key,
  workspace_id uuid references workspaces(id),
  provider text not null,
  livekit_trunk_id text,
  domain text,
  caller_id text,
  status text default 'active'
);

calls (
  id uuid primary key,
  workspace_id uuid references workspaces(id),
  agent_id uuid references agents(id),
  agent_version_id uuid references agent_versions(id),
  campaign_id uuid,
  campaign_contact_id uuid,
  direction text check (direction in ('inbound','outbound','browser')),
  phone_number text,
  room_name text,
  status text,
  started_at timestamptz,
  answered_at timestamptz,
  ended_at timestamptz,
  duration_seconds integer default 0,
  failure_reason text,
  retry_count integer default 0,
  recording_url text,
  summary text,
  sentiment text,
  disposition text,
  cost_usd numeric default 0
);

call_events (
  id uuid primary key,
  call_id uuid references calls(id),
  event_type text not null,
  payload jsonb default '{}'::jsonb,
  created_at timestamptz default now()
);

call_transcripts (
  id uuid primary key,
  call_id uuid references calls(id),
  role text check (role in ('user','assistant','tool','system')),
  content text not null,
  provider text,
  start_ms integer,
  end_ms integer
);
```

## Tools and Workflows

```sql
tools (
  id uuid primary key,
  workspace_id uuid references workspaces(id),
  name text not null,
  tool_type text not null,
  schema jsonb not null,
  config jsonb not null,
  enabled boolean default true
);

workflows (
  id uuid primary key,
  workspace_id uuid references workspaces(id),
  name text not null,
  description text,
  status text default 'draft'
);

workflow_steps (
  id uuid primary key,
  workflow_id uuid references workflows(id),
  step_order integer not null,
  step_type text check (step_type in ('call','whatsapp','email','webhook','delay')),
  config jsonb not null,
  delay_seconds integer default 0
);

workflow_transitions (
  id uuid primary key,
  workflow_id uuid references workflows(id),
  from_step_id uuid references workflow_steps(id),
  to_step_id uuid references workflow_steps(id),
  condition jsonb not null
);
```

## Campaigns

```sql
campaigns (
  id uuid primary key,
  workspace_id uuid references workspaces(id),
  name text not null,
  status text check (status in ('draft','scheduled','running','paused','completed','failed')),
  timezone text not null default 'Asia/Kolkata',
  quiet_hours jsonb,
  workflow_id uuid references workflows(id),
  agent_id uuid references agents(id),
  caller_id text,
  schedule_at timestamptz
);

campaign_contacts (
  id uuid primary key,
  campaign_id uuid references campaigns(id),
  name text,
  phone_number text not null,
  variables jsonb default '{}'::jsonb,
  status text default 'pending',
  last_call_id uuid references calls(id),
  attempts integer default 0,
  next_attempt_at timestamptz
);
```

## Knowledge Base

```sql
knowledge_bases (
  id uuid primary key,
  workspace_id uuid references workspaces(id),
  name text not null,
  description text
);

knowledge_documents (
  id uuid primary key,
  knowledge_base_id uuid references knowledge_bases(id),
  file_name text not null,
  storage_path text not null,
  status text default 'processing'
);

knowledge_chunks (
  id uuid primary key,
  document_id uuid references knowledge_documents(id),
  chunk_index integer not null,
  content text not null,
  embedding vector(1536),
  metadata jsonb default '{}'::jsonb
);

agent_knowledge_bases (
  agent_id uuid references agents(id),
  knowledge_base_id uuid references knowledge_bases(id),
  primary key (agent_id, knowledge_base_id)
);
```

## Billing and Admin

```sql
billing_plans (
  id uuid primary key,
  name text not null,
  monthly_price_inr numeric not null,
  included_minutes integer not null,
  overage_rate_inr numeric not null,
  features jsonb default '{}'::jsonb
);

subscriptions (
  id uuid primary key,
  workspace_id uuid references workspaces(id),
  plan_id uuid references billing_plans(id),
  provider text default 'razorpay',
  provider_customer_id text,
  provider_subscription_id text,
  status text not null,
  current_period_end timestamptz
);

credit_wallets (
  workspace_id uuid primary key references workspaces(id),
  balance_inr numeric not null default 0
);

usage_events (
  id uuid primary key,
  workspace_id uuid references workspaces(id),
  call_id uuid references calls(id),
  provider text,
  usage_type text,
  quantity numeric,
  unit text,
  cost_inr numeric,
  cost_usd numeric
);

invoices (
  id uuid primary key,
  workspace_id uuid references workspaces(id),
  amount_inr numeric not null,
  status text not null,
  provider_invoice_id text,
  invoice_url text
);

audit_logs (
  id uuid primary key,
  workspace_id uuid references workspaces(id),
  actor_user_id uuid references auth.users(id),
  action text not null,
  resource_type text not null,
  resource_id text,
  metadata jsonb default '{}'::jsonb,
  ip_address inet,
  user_agent text,
  created_at timestamptz default now()
);
```
