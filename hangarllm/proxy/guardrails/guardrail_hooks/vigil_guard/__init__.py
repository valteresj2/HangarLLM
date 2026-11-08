from typing import TYPE_CHECKING, Final

from hangarllm.types.guardrails import SupportedGuardrailIntegrations

from .vigil_guard import VigilGuardGuardrail

if TYPE_CHECKING:
    from hangarllm.types.guardrails import Guardrail, HangarllmParams


def initialize_guardrail(hangarllm_params: "HangarllmParams", guardrail: "Guardrail"):
    import hangarllm

    _vigil_guard_callback: Final = VigilGuardGuardrail(
        api_base=hangarllm_params.api_base,
        api_key=hangarllm_params.api_key,
        unreachable_fallback=hangarllm_params.unreachable_fallback,
        timeout=hangarllm_params.timeout,
        guardrail_name=guardrail.get("guardrail_name", ""),
        event_hook=hangarllm_params.mode,
        default_on=hangarllm_params.default_on,
    )
    hangarllm.logging_callback_manager.add_hangarllm_callback(_vigil_guard_callback)
    return _vigil_guard_callback


guardrail_initializer_registry: Final = {
    SupportedGuardrailIntegrations.VIGIL_GUARD.value: initialize_guardrail,
}


guardrail_class_registry: Final = {
    SupportedGuardrailIntegrations.VIGIL_GUARD.value: VigilGuardGuardrail,
}
