alter table public.call_logs add column if not exists sip_status text;
alter table public.call_logs add column if not exists sip_trunk_id text;

create index if not exists idx_call_logs_sip_failures
  on public.call_logs (created_at desc)
  where coalesce(failure_reason, '') <> '';
