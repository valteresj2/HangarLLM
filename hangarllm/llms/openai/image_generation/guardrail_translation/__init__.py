"""OpenAI Image Generation handler for Unified Guardrails."""

from typing import Final

from hangarllm.llms.openai.image_generation.guardrail_translation.handler import (
    OpenAIImageGenerationHandler,
)
from hangarllm.types.utils import CallTypes

guardrail_translation_mappings: Final = {
    CallTypes.image_generation: OpenAIImageGenerationHandler,
    CallTypes.aimage_generation: OpenAIImageGenerationHandler,
    CallTypes.image_edit: OpenAIImageGenerationHandler,
    CallTypes.aimage_edit: OpenAIImageGenerationHandler,
}

__all__ = ["OpenAIImageGenerationHandler", "guardrail_translation_mappings"]
