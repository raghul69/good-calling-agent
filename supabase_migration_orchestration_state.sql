-- Optional: orchestration brain persistence (upsert by call_id from the voice worker).
-- Run in Supabase SQL editor if you want [ORCHESTRATION_STATE] rows persisted.

create table if not exists public.orchestration_session_state (
  call_id text primary key,
  agent_id text,
  org_id text,
  user_id text,
  room_name text,
  transcript text,
  action_history text,
  call_status text not null default 'active',
  collected_fields text,
  updated_at timestamptz default now()
);

create index if not exists idx_orch_state_agent on public.orchestration_session_state (agent_id);
create index if not exists idx_orch_state_org on public.orchestration_session_state (org_id);

alter table public.orchestration_session_state enable row level security;

-- Service role bypasses RLS; tighten policies if exposing to anon/authenticated clients.

-- Additive columns for vertical packs (safe to run on existing DBs)
alter table public.orchestration_session_state add column if not exists vertical text;
alter table public.orchestration_session_state add column if not exists workflow_stage text;
alter table public.orchestration_session_state add column if not exists intent text;
alter table public.orchestration_session_state add column if not exists risk_level text;
alter table public.orchestration_session_state add column if not exists lead_score double precision;
alter table public.orchestration_session_state add column if not exists extracted_fields text;
