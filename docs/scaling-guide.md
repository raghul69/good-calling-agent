# Scaling Guide

## Scaling Goals

Target stages:

| Stage | Concurrency | Daily Calls | Architecture |
|---|---:|---:|---|
| MVP | 5-20 | 100-500 | Single Railway API + worker |
| Launch | 50-100 | 2K-10K | Split API, voice workers, Redis |
| Growth | 250-500 | 25K-100K | Worker pools, campaign queues, analytics workers |
| Enterprise | 1000+ | 250K+ | Multi-region workers, dedicated tenants, data residency |

## Voice Worker Scaling

Scale by LiveKit worker replicas:

- Run stateless worker containers.
- Workers register with LiveKit using same agent name.
- LiveKit dispatches jobs across workers.
- Use separate worker pools for:
  - browser tests
  - outbound calls
  - inbound calls
  - enterprise dedicated tenants

Recommended worker env:

```text
WORKER_CONCURRENCY=10
MAX_ACTIVE_CALLS_PER_WORKER=10
VOICE_MAX_COMPLETION_TOKENS=96
CALL_RETRY_POLL_SECONDS=60
```

## Campaign Scaling

Use queue-backed dispatch:

- `campaigns` queue for import and scheduling.
- `calls` queue for call dispatch.
- `post_call` queue for summarization and workflow advancement.
- `analytics` queue for rollups.

Rate limits:

- Per tenant calls/minute.
- Per SIP trunk concurrent calls.
- Per provider requests/minute.
- Per campaign daily cap.
- Per destination number retry cap.

## Database Scaling

Indexes:

- `calls(workspace_id, created_at desc)`
- `calls(agent_id, created_at desc)`
- `calls(campaign_id, status)`
- `campaign_contacts(campaign_id, status, next_attempt_at)`
- `usage_events(workspace_id, created_at desc)`
- `audit_logs(workspace_id, created_at desc)`
- `knowledge_chunks using ivfflat/hnsw on embedding`

Partition later:

- `calls` by month.
- `call_events` by month.
- `call_transcripts` by month.
- `usage_events` by month.

Retention:

- Raw transcripts: configurable, default 180 days.
- Recordings: configurable, default 90 days.
- Aggregates: indefinite.
- Audit logs: 1-7 years depending on plan.

## Provider Routing at Scale

Implement circuit breakers:

- Error rate threshold.
- Latency threshold.
- Budget threshold.
- Provider outage flag.

Fallback order example:

```text
LLM: Groq -> OpenAI -> Claude
STT: Sarvam -> Deepgram
TTS: Sarvam -> ElevenLabs
Telephony: LiveKit SIP/Vobiz -> Telnyx
```

## LiveKit and SIP Limits

Track:

- Active rooms.
- Active SIP participants.
- Call setup latency.
- Answered vs failed by trunk.
- Media connection failures.
- Egress recording failures.

For high-volume campaigns:

- Use multiple trunks/caller IDs.
- Spread starts over time.
- Apply regional quiet hours.
- Avoid blasting one carrier route.

## Cost Controls

Before call dispatch:

- Check subscription status.
- Check wallet balance.
- Check included minutes remaining.
- Estimate max call cost.
- Reserve credits for expected maximum call duration.

During call:

- Cap max duration.
- Cap max turns.
- Cap LLM output tokens.
- Use short TTS responses.

After call:

- Rate actual usage.
- Release unused reservation.
- Generate usage events.
