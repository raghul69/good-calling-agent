web: python -m uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1
worker: sh -c 'if [ "${VOICE_PIPELINE:-livekit_agents}" = "pipecat" ]; then python artifacts/agent-worker/pipecat_worker.py start || { echo "[PIPELINE_FAILOVER] pipeline=pipecat fallback=livekit_agents"; VOICE_PIPELINE=livekit_agents python -m backend.agent start; }; else python -m backend.agent start; fi'
