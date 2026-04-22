# Supabase Setup

Use this for production and local demo.

## 1. Project Keys

In Supabase, open Project Settings -> API and copy:

- Project URL -> `SUPABASE_URL`
- anon public key -> `SUPABASE_KEY`
- service_role secret key -> `SUPABASE_SERVICE_ROLE_KEY`

Keep `SUPABASE_SERVICE_ROLE_KEY` server-side only. Put it in `.env` locally and Render environment variables in production.

## 2. Database

Open SQL Editor -> New Query.

Paste and run:

```text
supabase_migration_v2.sql
```

That migration creates:

- `call_logs`
- `active_calls`
- `call_transcripts`
- owner-based RLS policies using `auth.uid() = user_id`
- private `call-recordings` bucket

Do not use allow-all policies for SaaS production.

## 3. Auth / OTP

Open Authentication -> URL Configuration:

- Site URL: `https://YOUR_RENDER_SERVICE.onrender.com`
- Redirect URLs:
  - `https://YOUR_RENDER_SERVICE.onrender.com/**`
  - `http://127.0.0.1:8001/**`
  - `http://localhost:8001/**`

Open Authentication -> Providers -> Email:

- Enable Email provider.
- Enable email OTP / magic link.
- Keep OTP rate limits at safe defaults.

If Supabase says you can request an OTP only after a number of seconds, wait for the cooldown. That is rate limiting, not an app crash.

## 4. Storage / Recordings

Create S3 access keys from Storage -> Settings -> S3 Access.

Set:

```text
SUPABASE_S3_ACCESS_KEY=...
SUPABASE_S3_SECRET_KEY=...
SUPABASE_S3_ENDPOINT=https://YOUR_PROJECT_REF.supabase.co/storage/v1/s3
SUPABASE_S3_REGION=ap-south-1
```

The migration keeps the bucket private. Recordings are stored under:

```text
recordings/<user_id>/<room>.ogg
```

## 5. Verify

Run:

```sql
select column_name, data_type
from information_schema.columns
where table_schema = 'public'
  and table_name = 'call_logs'
order by ordinal_position;
```

Confirm `user_id`, `phone`, `duration`, `summary`, and `recording_url` exist.
