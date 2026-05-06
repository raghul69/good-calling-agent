# Observability Plan

## Goals

Observability must answer:

- Is the platform online?
- Are calls connecting?
- Are callers hearing the AI?
- Are providers failing?
- Which tenant/campaign/agent caused cost or error spikes?
- Did billing and quota enforcement work?

## Signals

### Logs

All logs include:

- `request_id`
- `organization_id`
- `workspace_id`
- `user_id`
- `agent_id`
- `agent_version_id`
- `call_id`
- `campaign_id`
- `room_name`
- `provider`

Important log events:

- `api.request.started`
- `api.request.failed`
- `livekit.room.created`
- `livekit.agent.dispatched`
- `sip.participant.created`
- `agent.session.started`
- `agent.greeting.spoken`
- `stt.transcript.committed`
- `llm.response.generated`
- `tts.audio.generated`
- `tool.execution.started`
- `tool.execution.failed`
- `call.completed`
- `billing.usage.rated`
- `campaign.contact.advanced`

### Metrics

Platform:

- API p95 latency.
- API error rate.
- Worker active calls.
- Queue depth.
- Queue job latency.

Voice:

- Call setup latency.
- Answer rate.
- No-answer rate.
- SIP failure rate.
- Time to first audio.
- STT latency.
- LLM latency.
- TTS latency.
- Interrupt count.

Business:

- Calls per tenant.
- Minutes per tenant.
- Cost per tenant.
- Booking rate.
- Qualified lead rate.
- Campaign conversion.

Billing:

- Usage rated.
- Wallet balance.
- Failed renewals.
- Over-quota blocks.

### Traces

Trace one call end-to-end:

```text
POST /api/calls/outbound
  create_call
  create_livekit_room
  dispatch_agent
  worker_start
  sip_create_participant
  session_start
  greeting_tts
  transcript_stream
  tool_calls
  shutdown_summary
  billing_usage_rating
```

## Tools

Recommended:

- Sentry for API and worker errors.
- Railway logs and alerts.
- OpenTelemetry traces.
- Postgres metrics.
- Redis queue dashboard.
- LiveKit metrics/dashboard.
- Custom admin observability page.

## Dashboards

### Executive Dashboard

- Total calls.
- Answer rate.
- Minutes.
- Revenue.
- Gross margin.
- Active tenants.

### Operations Dashboard

- Live calls.
- Worker status.
- Queue depth.
- Provider health.
- Failed calls.
- Webhook failures.

### Tenant Dashboard

- Calls by agent.
- Calls by campaign.
- Cost/minute.
- Success rate.
- Sentiment.
- Bookings/leads.

## Alerts

Critical:

- API down.
- Worker not registered.
- SIP health false.
- LiveKit API unreachable.
- Queue depth above threshold.
- Call setup failure spike.
- Billing webhook verification failures.

Warning:

- TTS/STT provider latency spike.
- LLM fallback rate above threshold.
- Tenant near quota.
- Egress recording failures.

## QA Evidence

For each production call test store:

- test name
- phone number masked
- timestamp
- room name
- call ID
- expected greeting
- result
- log excerpts
- recording link if allowed
