-- P3–P5: contacts, campaigns, dial queue linkage, disposition, billing plans, usage helpers.
-- Existing `campaigns` table may lack columns — add additive columns only.

create extension if not exists "pgcrypto";

-- -----------------------------------------------------------------------------
-- Agents: inactive dispatch guard (paused)
-- -----------------------------------------------------------------------------
alter table public.agents add column if not exists agent_state text not null default 'active';
create index if not exists idx_agents_workspace_state on public.agents (workspace_id, agent_state);

-- -----------------------------------------------------------------------------
-- call_logs: CRM disposition alongside machine suffixes in summary (do not mutate summary)
-- -----------------------------------------------------------------------------
alter table public.call_logs add column if not exists manual_disposition text;
alter table public.call_logs add column if not exists manual_disposition_at timestamptz;

create index if not exists idx_call_logs_workspace_created on public.call_logs (workspace_id, created_at desc);

-- -----------------------------------------------------------------------------
-- contacts (relational CRM vs rollup)
-- -----------------------------------------------------------------------------
create table if not exists public.contacts (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces (id) on delete cascade,
  full_name text not null default '',
  phone_e164 text not null,
  tags text[] not null default '{}',
  source text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (workspace_id, phone_e164)
);

drop trigger if exists set_contacts_updated_at on public.contacts;
create trigger set_contacts_updated_at
before update on public.contacts
for each row execute function public.set_updated_at();

create index if not exists idx_contacts_workspace on public.contacts (workspace_id, created_at desc);

-- -----------------------------------------------------------------------------
-- campaigns (extend legacy table safely)
-- -----------------------------------------------------------------------------
create table if not exists public.campaigns (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.campaigns add column if not exists workspace_id uuid references public.workspaces (id) on delete cascade;
alter table public.campaigns add column if not exists name text not null default 'Campaign';
alter table public.campaigns add column if not exists description text not null default '';
alter table public.campaigns add column if not exists agent_id uuid references public.agents (id) on delete set null;
alter table public.campaigns add column if not exists status text not null default 'draft';
alter table public.campaigns add column if not exists schedule_cron text;
alter table public.campaigns add column if not exists started_at timestamptz;
alter table public.campaigns add column if not exists stopped_at timestamptz;
alter table public.campaigns add column if not exists total_calls integer not null default 0;
alter table public.campaigns add column if not exists completed_calls integer not null default 0;

drop trigger if exists set_campaigns_updated_at on public.campaigns;

drop trigger if exists set_campaigns_updated_at on public.campaigns;
create trigger set_campaigns_updated_at
before update on public.campaigns
for each row execute function public.set_updated_at();

-- -----------------------------------------------------------------------------
-- Dial queue linkage
-- -----------------------------------------------------------------------------
create table if not exists public.campaign_contacts (
  id uuid primary key default gen_random_uuid(),
  campaign_id uuid not null references public.campaigns (id) on delete cascade,
  contact_id uuid references public.contacts (id) on delete set null,
  phone_e164 text not null,
  status text not null default 'queued',
  attempt_count integer not null default 0,
  last_error text not null default '',
  call_log_id bigint references public.call_logs (id) on delete set null,
  queued_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (campaign_id, phone_e164)
);

drop trigger if exists set_campaign_contacts_updated_at on public.campaign_contacts;
create trigger set_campaign_contacts_updated_at
before update on public.campaign_contacts
for each row execute function public.set_updated_at();

create index if not exists idx_campaign_contacts_campaign_status on public.campaign_contacts (campaign_id, status);

-- -----------------------------------------------------------------------------
-- Plans (workspace-scoped entitlement)
-- -----------------------------------------------------------------------------
create table if not exists public.plans (
  id text primary key,
  label text not null default '',
  included_minutes numeric,
  max_contacts integer,
  max_campaigns integer,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

insert into public.plans (id, label, included_minutes, max_contacts, max_campaigns)
values
  ('free', 'Free', 60, 500, 2),
  ('starter', 'Starter', 250, 5000, 10),
  ('growth', 'Growth', null, null, null),
  ('enterprise', 'Enterprise', null, null, null)
on conflict (id) do nothing;

alter table public.workspace_settings add column if not exists plan_id text references public.plans (id);
alter table public.workspace_settings add column if not exists usage_counters jsonb not null default '{}'::jsonb;

-- -----------------------------------------------------------------------------
-- RLS: contacts, campaigns, campaign_contacts
-- -----------------------------------------------------------------------------
alter table public.contacts enable row level security;

drop policy if exists "contacts_select_member" on public.contacts;
create policy "contacts_select_member"
on public.contacts for select to authenticated
using (
  exists (
    select 1 from public.workspace_members wm
    where wm.workspace_id = contacts.workspace_id and wm.user_id = auth.uid()
  )
);

drop policy if exists "contacts_write_mutator" on public.contacts;
create policy "contacts_write_mutator"
on public.contacts for all to authenticated
using (
  exists (
    select 1 from public.workspace_members wm
    where wm.workspace_id = contacts.workspace_id
      and wm.user_id = auth.uid()
      and public.normalize_workspace_member_role(wm.role) in ('owner', 'admin', 'agent_manager')
  )
)
with check (
  exists (
    select 1 from public.workspace_members wm
    where wm.workspace_id = contacts.workspace_id
      and wm.user_id = auth.uid()
      and public.normalize_workspace_member_role(wm.role) in ('owner', 'admin', 'agent_manager')
  )
);

alter table public.campaigns enable row level security;

drop policy if exists "campaigns_select_member" on public.campaigns;
create policy "campaigns_select_member"
on public.campaigns for select to authenticated
using (
  workspace_id is not null
  and exists (
    select 1 from public.workspace_members wm
    where wm.workspace_id = campaigns.workspace_id and wm.user_id = auth.uid()
  )
);

drop policy if exists "campaigns_write_mutator" on public.campaigns;
create policy "campaigns_write_mutator"
on public.campaigns for all to authenticated
using (
  workspace_id is not null
  and exists (
    select 1 from public.workspace_members wm
    where wm.workspace_id = campaigns.workspace_id
      and wm.user_id = auth.uid()
      and public.normalize_workspace_member_role(wm.role) in ('owner', 'admin', 'agent_manager')
  )
)
with check (
  workspace_id is not null
  and exists (
    select 1 from public.workspace_members wm
    where wm.workspace_id = campaigns.workspace_id
      and wm.user_id = auth.uid()
      and public.normalize_workspace_member_role(wm.role) in ('owner', 'admin', 'agent_manager')
  )
);

alter table public.campaign_contacts enable row level security;

drop policy if exists "campaign_contacts_select_member" on public.campaign_contacts;
create policy "campaign_contacts_select_member"
on public.campaign_contacts for select to authenticated
using (
  exists (
    select 1
    from public.campaigns c
    join public.workspace_members wm on wm.workspace_id = c.workspace_id
    where c.id = campaign_contacts.campaign_id and wm.user_id = auth.uid()
  )
);

drop policy if exists "campaign_contacts_write_mutator" on public.campaign_contacts;
create policy "campaign_contacts_write_mutator"
on public.campaign_contacts for all to authenticated
using (
  exists (
    select 1
    from public.campaigns c
    join public.workspace_members wm on wm.workspace_id = c.workspace_id
    where c.id = campaign_contacts.campaign_id
      and wm.user_id = auth.uid()
      and public.normalize_workspace_member_role(wm.role) in ('owner', 'admin', 'agent_manager')
  )
)
with check (
  exists (
    select 1
    from public.campaigns c
    join public.workspace_members wm on wm.workspace_id = c.workspace_id
    where c.id = campaign_contacts.campaign_id
      and wm.user_id = auth.uid()
      and public.normalize_workspace_member_role(wm.role) in ('owner', 'admin', 'agent_manager')
  )
);

alter table public.plans enable row level security;

drop policy if exists "plans_select_authenticated" on public.plans;
create policy "plans_select_authenticated"
on public.plans for select to authenticated
using (true);
