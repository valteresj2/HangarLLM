"""
A2A to HangarLLM Completion Bridge.

This module provides transformation between A2A protocol messages and
HangarLLM completion API, enabling any HangarLLM-supported provider to be
invoked via the A2A protocol.
"""

from hangarllm.a2a_protocol.hangarllm_completion_bridge.handler import (
    A2ACompletionBridgeHandler,
    handle_a2a_completion,
    handle_a2a_completion_streaming,
)
from hangarllm.a2a_protocol.hangarllm_completion_bridge.transformation import (
    A2ACompletionBridgeTransformation,
)

__all__ = [
    "A2ACompletionBridgeHandler",
    "A2ACompletionBridgeTransformation",
    "handle_a2a_completion",
    "handle_a2a_completion_streaming",
]
