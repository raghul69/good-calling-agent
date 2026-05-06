# Security Checklist

## Authentication

- Supabase Auth enabled.
- Email OTP/password configured.
- JWT verified on every protected API route.
- Service role key never exposed to frontend.
- Admin routes require role check.

## Authorization

- Every tenant row has `workspace_id`.
- RLS enabled on tenant tables.
- API sets tenant context from authenticated user, never from client input.
- Roles:
  - owner
  - admin
  - developer
  - agent_manager
  - analyst
  - billing
  - member
- Role permissions are centralized.

## Secrets

- Store provider keys in Railway variables or encrypted `provider_accounts`.
- Never write secrets into `config.json`.
- Never log secrets.
- Use fingerprints for diagnostics.
- Rotate keys quarterly or after incident.

## Webhooks

- Verify Razorpay signatures.
- Verify Stripe signatures if Stripe remains enabled.
- Store idempotency keys/event IDs.
- Reject duplicate webhook processing.
- Log webhook failures with event type and provider ID only.

## Voice and Telephony

- Validate all phone numbers as E.164.
- Rate-limit per tenant, user, and destination number.
- Apply campaign quiet hours.
- Block premium/fraud destinations by country/prefix policy.
- Mask phone numbers in logs and UI where appropriate.

## Tools and Integrations

- Tool schemas are validated before publish.
- External API tools have timeout and retry caps.
- Tool URLs must pass allowlist rules.
- Secrets are referenced by ID, not embedded in prompt text.
- Tool responses are size-limited before entering LLM context.

## Prompt Security

- Separate system prompt, business prompt, and retrieved knowledge.
- Mark tool results as untrusted.
- Add prompt-injection guardrails for RAG content.
- Prevent agents from revealing secrets, internal prompts, or hidden config.

## Knowledge Base

- Scan uploads for allowed file types.
- Enforce file size limits.
- Store files per workspace.
- RLS on document metadata.
- Do not retrieve chunks from another workspace.

## Billing and Abuse

- Enforce quota before call dispatch.
- Reserve call credits before starting paid calls.
- Stop campaigns when wallet/subscription is invalid.
- Alert on abnormal cost spikes.

## Admin and Audit

- Record audit logs for:
  - login-sensitive changes
  - agent publish
  - provider key changes
  - SIP trunk changes
  - billing changes
  - role changes
  - campaign launch
- Audit logs are immutable to normal users.

## HTTP Security

- CORS restricted to known frontend domains.
- `X-Content-Type-Options: nosniff`.
- `X-Frame-Options: DENY`.
- `Referrer-Policy: strict-origin-when-cross-origin`.
- HSTS enabled on HTTPS.

## Production Gate

Before enterprise launch:

- Security review completed.
- RLS tests pass for cross-tenant isolation.
- Webhook replay/idempotency tests pass.
- Provider secret redaction tests pass.
- Rate-limit tests pass.
- Backup/restore drill completed.
- Incident runbook published.
