-- SaaS workspaces + tenant columns (run after supabase_migration_v2.sql in Supabase SQL Editor)
-- Idempotent-ish: safe to re-run if policies already exist (drops named policies first).

-- Extensions (usually already on in Supabase)
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 1) Core tenancy tables
CREATE TABLE IF NOT EXISTS public.workspaces (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL DEFAULT 'Workspace',
  created_by uuid REFERENCES auth.users (id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.workspace_members (
  workspace_id uuid NOT NULL REFERENCES public.workspaces (id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
  role text NOT NULL DEFAULT 'member' CHECK (role IN ('owner', 'admin', 'member')),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (workspace_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_workspace_members_user ON public.workspace_members (user_id);

CREATE TABLE IF NOT EXISTS public.workspace_settings (
  workspace_id uuid PRIMARY KEY REFERENCES public.workspaces (id) ON DELETE CASCADE,
  settings jsonb NOT NULL DEFAULT '{}'::jsonb,
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- 2) Tenant column on existing tables (nullable for backward compatibility)
ALTER TABLE public.call_logs
  ADD COLUMN IF NOT EXISTS workspace_id uuid REFERENCES public.workspaces (id) ON DELETE SET NULL;

ALTER TABLE public.active_calls
  ADD COLUMN IF NOT EXISTS workspace_id uuid REFERENCES public.workspaces (id) ON DELETE SET NULL;

ALTER TABLE public.call_transcripts
  ADD COLUMN IF NOT EXISTS workspace_id uuid REFERENCES public.workspaces (id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_call_logs_workspace ON public.call_logs (workspace_id);
CREATE INDEX IF NOT EXISTS idx_active_calls_workspace ON public.active_calls (workspace_id);
CREATE INDEX IF NOT EXISTS idx_call_transcripts_workspace ON public.call_transcripts (workspace_id);

-- 3) RLS
ALTER TABLE public.workspaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workspace_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workspace_settings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "workspaces_select_member" ON public.workspaces;
CREATE POLICY "workspaces_select_member"
  ON public.workspaces FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.workspace_members wm
      WHERE wm.workspace_id = workspaces.id AND wm.user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS "workspace_members_select_self" ON public.workspace_members;
CREATE POLICY "workspace_members_select_self"
  ON public.workspace_members FOR SELECT TO authenticated
  USING (user_id = auth.uid());

DROP POLICY IF EXISTS "workspace_settings_select_member" ON public.workspace_settings;
CREATE POLICY "workspace_settings_select_member"
  ON public.workspace_settings FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.workspace_members wm
      WHERE wm.workspace_id = workspace_settings.workspace_id AND wm.user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS "workspace_settings_update_admin" ON public.workspace_settings;
CREATE POLICY "workspace_settings_update_admin"
  ON public.workspace_settings FOR UPDATE TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.workspace_members wm
      WHERE wm.workspace_id = workspace_settings.workspace_id
        AND wm.user_id = auth.uid()
        AND wm.role IN ('owner', 'admin')
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.workspace_members wm
      WHERE wm.workspace_id = workspace_settings.workspace_id
        AND wm.user_id = auth.uid()
        AND wm.role IN ('owner', 'admin')
    )
  );

-- call_logs: legacy rows (workspace_id IS NULL) remain visible only to owner user_id;
-- workspace-scoped rows visible to all members of that workspace.
ALTER TABLE public.call_logs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "saas_call_logs_select" ON public.call_logs;
CREATE POLICY "saas_call_logs_select"
  ON public.call_logs FOR SELECT TO authenticated
  USING (
    (workspace_id IS NULL AND user_id IS NOT NULL AND auth.uid() = user_id)
    OR (
      workspace_id IS NOT NULL
      AND EXISTS (
        SELECT 1 FROM public.workspace_members wm
        WHERE wm.workspace_id = call_logs.workspace_id AND wm.user_id = auth.uid()
      )
    )
  );

-- active_calls + call_transcripts: same pattern
ALTER TABLE public.active_calls ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "saas_active_calls_select" ON public.active_calls;
CREATE POLICY "saas_active_calls_select"
  ON public.active_calls FOR SELECT TO authenticated
  USING (
    (workspace_id IS NULL AND user_id IS NOT NULL AND auth.uid() = user_id)
    OR (
      workspace_id IS NOT NULL
      AND EXISTS (
        SELECT 1 FROM public.workspace_members wm
        WHERE wm.workspace_id = active_calls.workspace_id AND wm.user_id = auth.uid()
      )
    )
  );

ALTER TABLE public.call_transcripts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "saas_call_transcripts_select" ON public.call_transcripts;
CREATE POLICY "saas_call_transcripts_select"
  ON public.call_transcripts FOR SELECT TO authenticated
  USING (
    (workspace_id IS NULL AND user_id IS NOT NULL AND auth.uid() = user_id)
    OR (
      workspace_id IS NOT NULL
      AND EXISTS (
        SELECT 1 FROM public.workspace_members wm
        WHERE wm.workspace_id = call_transcripts.workspace_id AND wm.user_id = auth.uid()
      )
    )
  );
