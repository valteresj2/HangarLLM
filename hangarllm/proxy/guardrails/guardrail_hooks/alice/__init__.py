from typing import TYPE_CHECKING, Final

from hangarllm.types.guardrails import SupportedGuardrailIntegrations

from .alice import AliceGuardrail

if TYPE_CHECKING:
    from hangarllm.types.guardrails import Guardrail, HangarllmParams


def initialize_guardrail(hangarllm_params: "HangarllmParams", guardrail: "Guardrail"):
    import hangarllm

    _alice_guardrail_callback: Final = AliceGuardrail(
        api_key=hangarllm_params.api_key,
        api_base=hangarllm_params.api_base,
        unreachable_fallback=getattr(hangarllm_params, "unreachable_fallback", "fail_closed"),
        guardrail_name=guardrail.get("guardrail_name", ""),
        event_hook=hangarllm_params.mode,
        default_on=hangarllm_params.default_on,
        timeout=hangarllm_params.timeout,
    )

    hangarllm.logging_callback_manager.add_hangarllm_callback(_alice_guardrail_callback)
    return _alice_guardrail_callback


guardrail_initializer_registry: Final = {
    SupportedGuardrailIntegrations.ALICE.value: initialize_guardrail,
}


guardrail_class_registry: Final = {
    SupportedGuardrailIntegrations.ALICE.value: AliceGuardrail,
}
