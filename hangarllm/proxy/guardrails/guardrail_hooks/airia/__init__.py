from typing import TYPE_CHECKING, Final

from hangarllm.proxy.guardrails.guardrail_hooks.airia.airia import AiriaGuardrail
from hangarllm.types.guardrails import SupportedGuardrailIntegrations

if TYPE_CHECKING:
    from hangarllm.types.guardrails import Guardrail, HangarllmParams


def initialize_guardrail(hangarllm_params: "HangarllmParams", guardrail: "Guardrail") -> AiriaGuardrail:
    import hangarllm

    _airia_callback: Final = AiriaGuardrail(
        api_base=hangarllm_params.api_base,
        api_key=hangarllm_params.api_key,
        timeout=hangarllm_params.timeout,
        guardrail_name=guardrail["guardrail_name"],
        event_hook=hangarllm_params.mode,
        default_on=hangarllm_params.default_on,
    )
    hangarllm.logging_callback_manager.add_hangarllm_callback(_airia_callback)

    return _airia_callback


guardrail_initializer_registry: Final = {
    SupportedGuardrailIntegrations.AIRIA.value: initialize_guardrail,
}

guardrail_class_registry: Final = {
    SupportedGuardrailIntegrations.AIRIA.value: AiriaGuardrail,
}
