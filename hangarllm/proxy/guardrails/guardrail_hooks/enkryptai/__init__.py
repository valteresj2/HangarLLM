from .enkryptai import EnkryptAIGuardrails

__all__ = ["EnkryptAIGuardrails"]


from typing import TYPE_CHECKING, Final

from hangarllm.types.guardrails import SupportedGuardrailIntegrations

if TYPE_CHECKING:
    from hangarllm.types.guardrails import Guardrail, HangarllmParams


def initialize_guardrail(hangarllm_params: "HangarllmParams", guardrail: "Guardrail"):
    import hangarllm

    _enkryptai_callback: Final = EnkryptAIGuardrails(
        guardrail_name=guardrail.get("guardrail_name", ""),
        api_key=hangarllm_params.api_key,
        api_base=hangarllm_params.api_base,
        policy_name=hangarllm_params.policy_name,
        deployment_name=hangarllm_params.deployment_name,
        detectors=hangarllm_params.detectors,
        block_on_violation=hangarllm_params.block_on_violation,
        event_hook=hangarllm_params.mode,
        default_on=hangarllm_params.default_on,
        timeout=hangarllm_params.timeout,
    )
    hangarllm.logging_callback_manager.add_hangarllm_callback(_enkryptai_callback)

    return _enkryptai_callback


guardrail_initializer_registry: Final = {
    SupportedGuardrailIntegrations.ENKRYPTAI.value: initialize_guardrail,
}


guardrail_class_registry: Final = {
    SupportedGuardrailIntegrations.ENKRYPTAI.value: EnkryptAIGuardrails,
}
