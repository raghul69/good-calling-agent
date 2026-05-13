alter table public.call_logs add column if not exists connected_at timestamptz;
alter table public.call_logs add column if not exists first_audio_at timestamptz;
alter table public.call_logs add column if not exists first_user_audio_at timestamptz;
alter table public.call_logs add column if not exists first_stt_at timestamptz;
alter table public.call_logs add column if not exists first_ai_reply_at timestamptz;
alter table public.call_logs add column if not exists silence_detected boolean not null default false;
alter table public.call_logs add column if not exists audio_issue_reason text;
