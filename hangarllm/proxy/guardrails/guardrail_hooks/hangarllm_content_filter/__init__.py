from typing import TYPE_CHECKING, Final, Optional

import hangarllm
from hangarllm.proxy.guardrails.guardrail_hooks.hangarllm_content_filter.content_filter import (
    ContentFilterGuardrail,
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
    Initialize the Content Filter Guardrail.

    Args:
        hangarllm_params: Guardrail configuration parameters
        guardrail: Guardrail metadata

    Returns:
        Initialized ContentFilterGuardrail instance
    """
    guardrail_name: Final = guardrail.get("guardrail_name")

    if not guardrail_name:
        raise ValueError("Content Filter: guardrail_name is required")

    content_filter_guardrail: Final = ContentFilterGuardrail(
        guardrail_name=guardrail_name,
        guardrail_id=guardrail.get("guardrail_id"),
        policy_template=guardrail.get("policy_template"),
        patterns=hangarllm_params.patterns,
        blocked_words=hangarllm_params.blocked_words,
        blocked_words_file=hangarllm_params.blocked_words_file,
        event_hook=hangarllm_params.mode,
        default_on=hangarllm_params.default_on or False,
        categories=getattr(hangarllm_params, "categories", None),
        severity_threshold=getattr(hangarllm_params, "severity_threshold", "medium"),
        llm_router=llm_router,
        image_model=getattr(hangarllm_params, "image_model", None),
        competitor_intent_config=getattr(hangarllm_params, "competitor_intent_config", None),
        end_session_after_n_fails=getattr(hangarllm_params, "end_session_after_n_fails", None),
        on_violation=getattr(hangarllm_params, "on_violation", None),
        realtime_violation_message=getattr(hangarllm_params, "realtime_violation_message", None),
    )

    hangarllm.logging_callback_manager.add_hangarllm_callback(content_filter_guardrail)

    return content_filter_guardrail


guardrail_initializer_registry: Final = {
    SupportedGuardrailIntegrations.HANGARLLM_CONTENT_FILTER.value: initialize_guardrail,
}


guardrail_class_registry: Final = {
    SupportedGuardrailIntegrations.HANGARLLM_CONTENT_FILTER.value: ContentFilterGuardrail,
}
