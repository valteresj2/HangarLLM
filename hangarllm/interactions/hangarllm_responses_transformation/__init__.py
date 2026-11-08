"""
Bridge module for connecting Interactions API to Responses API via hangarllm.responses().
"""

from hangarllm.interactions.hangarllm_responses_transformation.handler import (
    HangarLLMResponsesInteractionsHandler,
)
from hangarllm.interactions.hangarllm_responses_transformation.transformation import (
    HangarLLMResponsesInteractionsConfig,
)

__all__ = [
    "HangarLLMResponsesInteractionsConfig",  # Transformation config class (not BaseInteractionsAPIConfig)
    "HangarLLMResponsesInteractionsHandler",
]
