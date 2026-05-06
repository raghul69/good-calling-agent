"""Compatibility exports for the realtime voice pipeline.

New code should import from `backend.fast_voice_router` and
`backend.conversation_state` directly.
"""

from backend.conversation_state import ConversationStage, FastRouteResult, FastVoiceState
from backend.fast_voice_router import FastVoiceRouter

__all__ = ["ConversationStage", "FastRouteResult", "FastVoiceState", "FastVoiceRouter"]
