"""OpenAI Audio Transcription handler for Unified Guardrails."""

from typing import Final

from hangarllm.llms.openai.transcriptions.guardrail_translation.handler import (
    OpenAIAudioTranscriptionHandler,
)
from hangarllm.types.utils import CallTypes

guardrail_translation_mappings: Final = {
    CallTypes.transcription: OpenAIAudioTranscriptionHandler,
    CallTypes.atranscription: OpenAIAudioTranscriptionHandler,
}

__all__ = ["OpenAIAudioTranscriptionHandler", "guardrail_translation_mappings"]
