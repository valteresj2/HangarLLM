from typing import TYPE_CHECKING, Final

from hangarllm.types.guardrails import SupportedGuardrailIntegrations

from .deepkeep import DeepKeepGuardrail

if TYPE_CHECKING:
    from hangarllm.types.guardrails import Guardrail, HangarllmParams


def initialize_guardrail(hangarllm_params: "HangarllmParams", guardrail: "Guardrail"):
    import hangarllm

    _deepkeep_guardrail_callback: Final = DeepKeepGuardrail(
        api_base=hangarllm_params.api_base,
        api_key=hangarllm_params.api_key,
        firewall_id=getattr(hangarllm_params, "deepkeep_firewall_id", None),
        unreachable_fallback=getattr(hangarllm_params, "unreachable_fallback", "fail_closed"),
        extra_headers=getattr(hangarllm_params, "extra_headers", None),
        guardrail_name=guardrail.get("guardrail_name", ""),
        event_hook=hangarllm_params.mode,
        default_on=hangarllm_params.default_on,
        timeout=hangarllm_params.timeout,
    )

    hangarllm.logging_callback_manager.add_hangarllm_callback(_deepkeep_guardrail_callback)
    return _deepkeep_guardrail_callback


guardrail_initializer_registry: Final = {
    SupportedGuardrailIntegrations.DEEPKEEP.value: initialize_guardrail,
}


guardrail_class_registry: Final = {
    SupportedGuardrailIntegrations.DEEPKEEP.value: DeepKeepGuardrail,
}
