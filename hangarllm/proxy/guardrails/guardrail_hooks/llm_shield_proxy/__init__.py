from typing import TYPE_CHECKING, Final

from hangarllm.types.guardrails import SupportedGuardrailIntegrations

from .llm_shield_proxy import LLMShieldProxyGuardrail

if TYPE_CHECKING:
    from hangarllm.types.guardrails import Guardrail, HangarllmParams


def initialize_guardrail(hangarllm_params: "HangarllmParams", guardrail: "Guardrail") -> LLMShieldProxyGuardrail:
    import hangarllm

    _llm_shield_guardrail_callback: Final = LLMShieldProxyGuardrail(
        api_key=hangarllm_params.api_key,
        api_base=hangarllm_params.api_base,
        guardrail_name=guardrail.get("guardrail_name", ""),
        event_hook=hangarllm_params.mode,
        default_on=hangarllm_params.default_on,
    )

    hangarllm.logging_callback_manager.add_hangarllm_callback(_llm_shield_guardrail_callback)
    return _llm_shield_guardrail_callback


guardrail_initializer_registry: Final = {
    SupportedGuardrailIntegrations.LLM_SHIELD_PROXY.value: initialize_guardrail,
}


guardrail_class_registry: Final = {
    SupportedGuardrailIntegrations.LLM_SHIELD_PROXY.value: LLMShieldProxyGuardrail,
}
