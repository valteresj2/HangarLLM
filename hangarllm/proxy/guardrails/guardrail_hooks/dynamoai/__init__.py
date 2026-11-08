from typing import TYPE_CHECKING, Final

from hangarllm.types.guardrails import SupportedGuardrailIntegrations

from .dynamoai import DynamoAIGuardrails

if TYPE_CHECKING:
    from hangarllm.types.guardrails import Guardrail, HangarllmParams


def initialize_guardrail(hangarllm_params: "HangarllmParams", guardrail: "Guardrail"):
    import hangarllm

    _dynamoai_callback: Final = DynamoAIGuardrails(
        api_base=hangarllm_params.api_base,
        api_key=hangarllm_params.api_key,
        guardrail_name=guardrail.get("guardrail_name", ""),
        event_hook=hangarllm_params.mode,
        default_on=hangarllm_params.default_on,
        timeout=hangarllm_params.timeout,
    )
    hangarllm.logging_callback_manager.add_hangarllm_callback(_dynamoai_callback)

    return _dynamoai_callback


guardrail_initializer_registry: Final = {
    SupportedGuardrailIntegrations.DYNAMOAI.value: initialize_guardrail,
}


guardrail_class_registry: Final = {
    SupportedGuardrailIntegrations.DYNAMOAI.value: DynamoAIGuardrails,
}
