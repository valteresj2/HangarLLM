from typing import TYPE_CHECKING, Final

from hangarllm.types.guardrails import SupportedGuardrailIntegrations

from .xecguard import XecGuardGuardrail

if TYPE_CHECKING:
    from hangarllm.types.guardrails import Guardrail, HangarllmParams


def initialize_guardrail(
    hangarllm_params: "HangarllmParams",
    guardrail: "Guardrail",
):
    import hangarllm

    _cb: Final = XecGuardGuardrail(
        api_base=hangarllm_params.api_base,
        api_key=hangarllm_params.api_key,
        xecguard_model=hangarllm_params.xecguard_model,
        policy_names=hangarllm_params.policy_names,
        block_on_error=hangarllm_params.block_on_error,
        grounding_strictness=hangarllm_params.grounding_strictness,
        guardrail_name=guardrail.get(
            "guardrail_name",
            "",
        ),
        event_hook=hangarllm_params.mode,
        default_on=hangarllm_params.default_on,
        timeout=hangarllm_params.timeout,
    )
    hangarllm.logging_callback_manager.add_hangarllm_callback(
        _cb,
    )

    return _cb


guardrail_initializer_registry: Final = {
    SupportedGuardrailIntegrations.XECGUARD.value: initialize_guardrail,
}


guardrail_class_registry: Final = {
    SupportedGuardrailIntegrations.XECGUARD.value: XecGuardGuardrail,
}
