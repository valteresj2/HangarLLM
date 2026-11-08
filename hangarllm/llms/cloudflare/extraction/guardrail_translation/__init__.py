from typing import Final

from hangarllm.llms.cloudflare.extraction.guardrail_translation.handler import ExtractionHandler
from hangarllm.types.utils import CallTypes

guardrail_translation_mappings: Final = {
    CallTypes.extraction: ExtractionHandler,
    CallTypes.aextraction: ExtractionHandler,
}

__all__ = ["ExtractionHandler", "guardrail_translation_mappings"]
