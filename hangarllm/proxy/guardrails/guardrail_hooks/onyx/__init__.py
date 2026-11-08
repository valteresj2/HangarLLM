from typing import TYPE_CHECKING, Final

from hangarllm.proxy.guardrails.guardrail_hooks.onyx.onyx import OnyxGuardrail
from hangarllm.types.guardrails import SupportedGuardrailIntegrations

if TYPE_CHECKING:
    from hangarllm.types.guardrails import Guardrail, HangarllmParams


def initialize_guardrail(hangarllm_params: "HangarllmParams", guardrail: "Guardrail"):
    import hangarllm

    _onyx_callback: Final = OnyxGuardrail(
        api_base=hangarllm_params.api_base,
        api_key=hangarllm_params.api_key,
        guardrail_name=guardrail.get("guardrail_name", ""),
        event_hook=hangarllm_params.mode,
        default_on=hangarllm_params.default_on,
        timeout=hangarllm_params.timeout,
    )
    hangarllm.logging_callback_manager.add_hangarllm_callback(_onyx_callback)

    return _onyx_callback


guardrail_initializer_registry: Final = {
    SupportedGuardrailIntegrations.ONYX.value: initialize_guardrail,
}


guardrail_class_registry: Final = {
    SupportedGuardrailIntegrations.ONYX.value: OnyxGuardrail,
}
