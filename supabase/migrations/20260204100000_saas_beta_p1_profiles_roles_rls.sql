-- P1: profiles, workspace display fields, workspace role normalization helpers,
-- RLS tightening (agent_manager), call_logs/workspace_settings/workspace_members/workspaces policies.
-- Applies idempotently alongside existing agent_foundation migrations.

create extension if not exists "pgcrypto";

-- -----------------------------------------------------------------------------
-- Profiles
-- -----------------------------------------------------------------------------
create table if not exists public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  display_name text,
  avatar_url text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

drop trigger if exists set_profiles_updated_at on public.profiles;
create trigger set_profiles_updated_at
before update on public.profiles
for each row execute function public.set_updated_at();

alter table public.profiles enable row level security;

drop policy if exists "profiles_select_self" on public.profiles;
create policy "profiles_select_self"
on public.profiles for select to authenticated
using (id = auth.uid());

drop policy if exists "profiles_update_self" on public.profiles;
create policy "profiles_update_self"
on public.profiles for update to authenticated
using (id = auth.uid())
with check (id = auth.uid());

drop policy if exists "profiles_insert_self" on public.profiles;
create policy "profiles_insert_self"
on public.profiles for insert to authenticated
with check (id = auth.uid());

-- -----------------------------------------------------------------------------
-- Workspace metadata
-- -----------------------------------------------------------------------------
alter table public.workspaces add column if not exists slug text unique;
alter table public.workspaces add column if not exists billing_email text;

-- -----------------------------------------------------------------------------
-- Role normalization / app-level enum (validated in app); DB keeps text.
-- -----------------------------------------------------------------------------
update public.workspace_members set role = 'viewer' where lower(role) = 'member';

create or replace function public.normalize_workspace_member_role(r text)
returns text
language sql
immutable
as $$
  select case lower(coalesce(r, ''))
    when 'owner' then 'owner'
    when 'admin' then 'admin'
    when 'agent_manager' then 'agent_manager'
    when 'member' then 'viewer'
    when 'viewer' then 'viewer'
    else 'viewer'
  end;
$$;

-- -----------------------------------------------------------------------------
-- Replace agent/agent_version write policies to allow agent_manager + admin + owner
-- -----------------------------------------------------------------------------
drop policy if exists "agent_foundation_agents_write_admin" on public.agents;
create policy "agent_foundation_agents_write_mutators"
on public.agents for all to authenticated
using (
  exists (
    select 1 from public.workspace_members wm
    where wm.workspace_id = agents.workspace_id
      and wm.user_id = auth.uid()
      and public.normalize_workspace_member_role(wm.role) in ('owner', 'admin', 'agent_manager')
  )
)
with check (
  exists (
    select 1 from public.workspace_members wm
    where wm.workspace_id = agents.workspace_id
      and wm.user_id = auth.uid()
      and public.normalize_workspace_member_role(wm.role) in ('owner', 'admin', 'agent_manager')
  )
);

drop policy if exists "agent_foundation_versions_write_admin" on public.agent_versions;
create policy "agent_foundation_versions_write_mutators"
on public.agent_versions for all to authenticated
using (
  exists (
    select 1
    from public.agents a
    join public.workspace_members wm on wm.workspace_id = a.workspace_id
    where a.id = agent_versions.agent_id
      and wm.user_id = auth.uid()
      and public.normalize_workspace_member_role(wm.role) in ('owner', 'admin', 'agent_manager')
  )
)
with check (
  exists (
    select 1
    from public.agents a
    join public.workspace_members wm on wm.workspace_id = a.workspace_id
    where a.id = agent_versions.agent_id
      and wm.user_id = auth.uid()
      and public.normalize_workspace_member_role(wm.role) in ('owner', 'admin', 'agent_manager')
  )
);

drop policy if exists "agent_foundation_shares_write_admin" on public.agent_shares;
create policy "agent_foundation_shares_write_owner_admin"
on public.agent_shares for all to authenticated
using (
  exists (
    select 1
    from public.agents a
    join public.workspace_members wm on wm.workspace_id = a.workspace_id
    where a.id = agent_shares.agent_id
      and wm.user_id = auth.uid()
      and public.normalize_workspace_member_role(wm.role) in ('owner', 'admin')
  )
)
with check (
  exists (
    select 1
    from public.agents a
    join public.workspace_members wm on wm.workspace_id = a.workspace_id
    where a.id = agent_shares.agent_id
      and wm.user_id = auth.uid()
      and public.normalize_workspace_member_role(wm.role) in ('owner', 'admin')
  )
);

-- -----------------------------------------------------------------------------
-- call_logs RLS (JWT path; service_role bypasses)
-- -----------------------------------------------------------------------------
alter table public.call_logs enable row level security;

drop policy if exists "call_logs_select_workspace" on public.call_logs;
create policy "call_logs_select_workspace"
on public.call_logs for select to authenticated
using (
  workspace_id is not null
  and exists (
    select 1 from public.workspace_members wm
    where wm.workspace_id = call_logs.workspace_id and wm.user_id = auth.uid()
  )
);

drop policy if exists "call_logs_update_workspace_admin" on public.call_logs;
create policy "call_logs_update_workspace_feedback"
on public.call_logs for update to authenticated
using (
  workspace_id is not null
  and exists (
    select 1 from public.workspace_members wm
    where wm.workspace_id = call_logs.workspace_id
      and wm.user_id = auth.uid()
      and public.normalize_workspace_member_role(wm.role) in ('owner', 'admin', 'agent_manager')
  )
)
with check (
  workspace_id is not null
  and exists (
    select 1 from public.workspace_members wm
    where wm.workspace_id = call_logs.workspace_id
      and wm.user_id = auth.uid()
      and public.normalize_workspace_member_role(wm.role) in ('owner', 'admin', 'agent_manager')
  )
);

-- -----------------------------------------------------------------------------
-- workspace_settings RLS
-- -----------------------------------------------------------------------------
alter table public.workspace_settings enable row level security;

drop policy if exists "workspace_settings_select_member" on public.workspace_settings;
create policy "workspace_settings_select_member"
on public.workspace_settings for select to authenticated
using (
  exists (
    select 1 from public.workspace_members wm
    where wm.workspace_id = workspace_settings.workspace_id and wm.user_id = auth.uid()
  )
);

drop policy if exists "workspace_settings_write_admin" on public.workspace_settings;
create policy "workspace_settings_write_admin"
on public.workspace_settings for all to authenticated
using (
  exists (
    select 1 from public.workspace_members wm
    where wm.workspace_id = workspace_settings.workspace_id
      and wm.user_id = auth.uid()
      and public.normalize_workspace_member_role(wm.role) in ('owner', 'admin')
  )
)
with check (
  exists (
    select 1 from public.workspace_members wm
    where wm.workspace_id = workspace_settings.workspace_id
      and wm.user_id = auth.uid()
      and public.normalize_workspace_member_role(wm.role) in ('owner', 'admin')
  )
);

-- -----------------------------------------------------------------------------
-- workspaces + workspace_members selective RLS (read membership)
-- -----------------------------------------------------------------------------
alter table public.workspace_members enable row level security;

drop policy if exists "workspace_members_select_self" on public.workspace_members;
create policy "workspace_members_select_self"
on public.workspace_members for select to authenticated
using (user_id = auth.uid());

drop policy if exists "workspace_members_select_same_workspace" on public.workspace_members;
create policy "workspace_members_select_same_workspace"
on public.workspace_members for select to authenticated
using (
  exists (
    select 1 from public.workspace_members self_wm
    where self_wm.workspace_id = workspace_members.workspace_id
      and self_wm.user_id = auth.uid()
  )
);

alter table public.workspaces enable row level security;

drop policy if exists "workspaces_select_member" on public.workspaces;
create policy "workspaces_select_member"
on public.workspaces for select to authenticated
using (
  exists (
    select 1 from public.workspace_members wm
    where wm.workspace_id = workspaces.id and wm.user_id = auth.uid()
  )
);
