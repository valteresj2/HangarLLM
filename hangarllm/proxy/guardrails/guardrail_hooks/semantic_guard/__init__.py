"""
Semantic Guard guardrail — embedding-based prompt injection detection.

Uses semantic-router to match user prompts against known attack patterns.
"""

from typing import TYPE_CHECKING, Final, Optional

import hangarllm
from hangarllm.constants import (
    DEFAULT_SEMANTIC_GUARD_EMBEDDING_MODEL,
    DEFAULT_SEMANTIC_GUARD_SIMILARITY_THRESHOLD,
)
from hangarllm.proxy.guardrails.guardrail_hooks.semantic_guard.semantic_guard import (
    SemanticGuardrail,
)
from hangarllm.types.guardrails import SupportedGuardrailIntegrations

if TYPE_CHECKING:
    from hangarllm import Router
    from hangarllm.types.guardrails import Guardrail, HangarllmParams


def initialize_guardrail(
    hangarllm_params: "HangarllmParams",
    guardrail: "Guardrail",
    llm_router: Optional["Router"] = None,
):
    """
    Initialize the Semantic Guard guardrail.

    Args:
        hangarllm_params: Guardrail configuration parameters
        guardrail: Guardrail metadata
        llm_router: HangarLLM Router instance (required for embeddings)

    Returns:
        Initialized SemanticGuardrail instance
    """
    guardrail_name: Final = guardrail.get("guardrail_name")
    if not guardrail_name:
        raise ValueError("SemanticGuard: guardrail_name is required")

    if llm_router is None:
        raise ValueError(
            "SemanticGuard requires llm_router for embeddings. Configure a model_list with an embedding model."
        )

    semantic_guardrail: Final = SemanticGuardrail(
        guardrail_name=guardrail_name,
        llm_router=llm_router,
        embedding_model=getattr(hangarllm_params, "embedding_model", None) or DEFAULT_SEMANTIC_GUARD_EMBEDDING_MODEL,
        similarity_threshold=getattr(hangarllm_params, "similarity_threshold", None)
        or DEFAULT_SEMANTIC_GUARD_SIMILARITY_THRESHOLD,
        route_templates=getattr(hangarllm_params, "route_templates", None),
        custom_routes_file=getattr(hangarllm_params, "custom_routes_file", None),
        custom_routes=getattr(hangarllm_params, "custom_routes", None),
        on_flagged_action=getattr(hangarllm_params, "on_flagged_action", "block"),
        event_hook=hangarllm_params.mode,
        default_on=hangarllm_params.default_on or False,
    )

    hangarllm.logging_callback_manager.add_hangarllm_callback(semantic_guardrail)

    return semantic_guardrail


guardrail_initializer_registry: Final = {
    SupportedGuardrailIntegrations.SEMANTIC_GUARD.value: initialize_guardrail,
}

guardrail_class_registry: Final = {
    SupportedGuardrailIntegrations.SEMANTIC_GUARD.value: SemanticGuardrail,
}
