-- Production call gate: expose a stable published UUID on agents and keep
-- a config_json compatibility column for deployment checks.

alter table public.agents
  add column if not exists published_agent_uuid uuid;

alter table public.agents
  add column if not exists config_json jsonb not null default '{}'::jsonb;

create unique index if not exists idx_agents_published_agent_uuid
  on public.agents (published_agent_uuid)
  where published_agent_uuid is not null;
