from typing import TYPE_CHECKING, Final

from hangarllm.types.guardrails import SupportedGuardrailIntegrations

from .qualifire import QualifireGuardrail

if TYPE_CHECKING:
    from hangarllm.types.guardrails import Guardrail, HangarllmParams


def initialize_guardrail(hangarllm_params: "HangarllmParams", guardrail: "Guardrail"):
    import hangarllm

    _qualifire_callback: Final = QualifireGuardrail(
        api_key=hangarllm_params.api_key,
        api_base=hangarllm_params.api_base,
        evaluation_id=getattr(hangarllm_params, "evaluation_id", None),
        prompt_injections=getattr(hangarllm_params, "prompt_injections", None),
        hallucinations_check=getattr(hangarllm_params, "hallucinations_check", None),
        grounding_check=getattr(hangarllm_params, "grounding_check", None),
        pii_check=getattr(hangarllm_params, "pii_check", None),
        content_moderation_check=getattr(hangarllm_params, "content_moderation_check", None),
        tool_selection_quality_check=getattr(hangarllm_params, "tool_selection_quality_check", None),
        assertions=getattr(hangarllm_params, "assertions", None),
        on_flagged=getattr(hangarllm_params, "on_flagged", "block"),
        guardrail_name=guardrail.get("guardrail_name", ""),
        event_hook=hangarllm_params.mode,
        default_on=hangarllm_params.default_on,
        timeout=hangarllm_params.timeout,
    )

    hangarllm.logging_callback_manager.add_hangarllm_callback(_qualifire_callback)

    return _qualifire_callback


guardrail_initializer_registry: Final = {
    SupportedGuardrailIntegrations.QUALIFIRE.value: initialize_guardrail,
}


guardrail_class_registry: Final = {
    SupportedGuardrailIntegrations.QUALIFIRE.value: QualifireGuardrail,
}
