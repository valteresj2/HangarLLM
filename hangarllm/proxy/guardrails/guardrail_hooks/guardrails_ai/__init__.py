from typing import TYPE_CHECKING, Final

from hangarllm.types.guardrails import SupportedGuardrailIntegrations

from .guardrails_ai import GuardrailsAI

if TYPE_CHECKING:
    from hangarllm.types.guardrails import Guardrail, HangarllmParams


def initialize_guardrail(hangarllm_params: "HangarllmParams", guardrail: "Guardrail"):
    import hangarllm

    if hangarllm_params.guard_name is None:
        raise Exception(
            "GuardrailsAIException - Please pass the Guardrails AI guard name via 'hangarllm_params::guard_name'"
        )

    _guardrails_ai_callback: Final = GuardrailsAI(
        api_base=hangarllm_params.api_base,
        api_key=hangarllm_params.api_key,
        guardrail_name=guardrail.get("guardrail_name", ""),
        event_hook=hangarllm_params.mode,
        default_on=hangarllm_params.default_on,
        guard_name=hangarllm_params.guard_name,
        guardrails_ai_api_input_format=getattr(hangarllm_params, "guardrails_ai_api_input_format", "llmOutput"),
        timeout=hangarllm_params.timeout,
    )
    hangarllm.logging_callback_manager.add_hangarllm_callback(_guardrails_ai_callback)

    return _guardrails_ai_callback


guardrail_initializer_registry: Final = {
    SupportedGuardrailIntegrations.GUARDRAILS_AI.value: initialize_guardrail,
}


guardrail_class_registry: Final = {
    SupportedGuardrailIntegrations.GUARDRAILS_AI.value: GuardrailsAI,
}
