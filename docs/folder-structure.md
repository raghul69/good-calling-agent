# Folder Structure

## Target Monorepo

```text
apps/
  web/
    app/
      (auth)/
      (dashboard)/
        agents/
        calls/
        campaigns/
        workflows/
        knowledge-base/
        analytics/
        billing/
        admin/
        settings/
      api-proxy/
    components/
      agents/
      audio/
      billing/
      campaigns/
      charts/
      calls/
      layout/
      providers/
      workflows/
    lib/
      api-client.ts
      auth.ts
      format.ts
      permissions.ts
    styles/
    tests/

  api/
    backend/
      main.py
      auth/
      billing/
      calls/
      campaigns/
      integrations/
      knowledge/
      observability/
      orgs/
      providers/
      sip/
      tools/
      workflows/
      workers/
    migrations/
    tests/

  voice-worker/
    worker.py
    runtime/
      agent_session.py
      provider_router.py
      prompt_builder.py
      tool_executor.py
      transcript_stream.py
    tests/

  campaign-worker/
    worker.py
    jobs/
      import_contacts.py
      dispatch_call.py
      retry_call.py
      advance_workflow.py
      aggregate_campaign.py
    tests/

packages/
  schemas/
    openapi/
    json-schema/
  shared/
    permissions/
    provider-catalog/
    pricing/
  ui/
    shadcn/
    charts/

infra/
  docker/
  railway/
  vercel/
  supabase/
  redis/

docs/
  final-architecture.md
  folder-structure.md
  backend-module-map.md
  db-schema.md
  deployment-guide.md
  scaling-guide.md
  observability-plan.md
  security-checklist.md
  saas-roadmap.md
```

## Current Repo Migration Path

The current repo can evolve without a big-bang rewrite:

```text
backend/
  main.py                  -> split into routers/services over time
  db.py                    -> split into repositories
  agent.py                 -> move to apps/voice-worker
frontend/
  src/App.tsx              -> migrate route by route to Next.js app directory
supabase_migration*.sql    -> move to apps/api/migrations or infra/supabase
Dockerfile                 -> keep for Railway backend/worker image
railway.toml               -> keep backend deploy config
```

## Naming Rules

- `agent` means reusable AI assistant configuration.
- `agent_version` means immutable published runtime config.
- `call` means one conversation/session.
- `campaign` means a scheduled/bulk execution.
- `workflow` means reusable sequence logic.
- `tool` means an external callable action.
- `provider` means LLM/STT/TTS/telephony vendor.
