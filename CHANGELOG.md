# Changelog

## 2026-05-04

- Shipped the Agent Foundation slice: versioned agent persistence, import/export, duplicate, publish, runtime config resolution, provider usage events, and audit logging.
- Added protected FastAPI agent/version APIs, provider options, and LiveKit dispatch metadata for `agent_id`, `agent_version_id`, and resolved agent config.
- Updated the worker runtime to use saved agent config, Tamil/Tanglish prompts, Gemini routing, and provider usage logging.
- Added `supabase_migration_agent_foundation.sql`; apply it after the v2, SaaS workspace, and production hardening migrations.
- Production behavior: DB-backed agents require a published version before calls use saved config; legacy non-UUID agent IDs still fall back to env/default config.
- Verified with `python -m compileall backend`, `python -m pytest backend/tests/test_main.py -q`, `npm.cmd --prefix frontend test`, `npm.cmd --prefix frontend run build`, and `git diff --check` with only Windows LF/CRLF warnings.
