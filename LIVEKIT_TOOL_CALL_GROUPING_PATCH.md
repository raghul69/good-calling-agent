# LiveKit Tool-Call Grouping Patch

This worker applies a runtime monkey-patch for LiveKit Agents tool-call grouping.

## Problem

Some LLM or provider paths may reuse the same `call_id` across back-to-back tool calls. The upstream grouping logic maps each `call_id` to a single group, so repeated IDs can overwrite earlier groups. That can attach tool outputs to the wrong function call and produce warnings such as:

```text
function call missing the corresponding function output
```

## Fix

`backend/livekit_group_tool_calls_fix.py` overrides the effective `group_tool_calls` implementation by patching `livekit.agents.llm._provider_format.utils.group_tool_calls`. The patched implementation keeps ordered groups per `call_id` and assigns each output to the next matching group in sequence, preventing the last duplicated ID from winning.

Provider modules that imported the original function are rebound dynamically with `pkgutil.iter_modules`, so current and future modules under `livekit.agents.llm._provider_format` are covered when they expose `group_tool_calls`.

## Startup Behavior

`backend/agent.py` applies the patch during worker startup before importing the LiveKit agent APIs. The startup hook is guarded with `try` / `except`, so future SDK layout changes do not prevent the worker from starting; they log a warning that tool batching may be unreliable.

## Scope

This specifically stabilizes LLM tool-call batching and chat-context grouping. It does not address SIP dialing, room connection, LiveKit auth, TTS, STT, or unrelated provider/runtime issues.

## Upgrade Hygiene

This project currently pins `livekit-agents==1.4.2` in `requirements.txt`. As of the current upstream `main` branch, LiveKit still uses the single `call_id` to group mapping in `livekit.agents.llm._provider_format.utils.group_tool_calls`, so this patch should remain in place.

When upgrading `livekit-agents`, re-check upstream `group_tool_calls`. If upstream changes to preserve multiple groups per repeated `call_id`, remove `backend/livekit_group_tool_calls_fix.py` and the guarded startup call in `backend/agent.py`.
