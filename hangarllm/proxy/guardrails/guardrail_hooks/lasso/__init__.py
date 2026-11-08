from typing import TYPE_CHECKING, Final

from hangarllm.types.guardrails import SupportedGuardrailIntegrations

from .lasso import LassoGuardrail

if TYPE_CHECKING:
    from hangarllm.types.guardrails import Guardrail, HangarllmParams


def initialize_guardrail(hangarllm_params: "HangarllmParams", guardrail: "Guardrail"):
    import hangarllm

    _lasso_callback: Final = LassoGuardrail(
        guardrail_name=guardrail.get("guardrail_name", ""),
        api_key=hangarllm_params.api_key,
        api_base=hangarllm_params.api_base,
        user_id=hangarllm_params.lasso_user_id,
        conversation_id=hangarllm_params.lasso_conversation_id,
        event_hook=hangarllm_params.mode,
        default_on=hangarllm_params.default_on,
        timeout=hangarllm_params.timeout,
    )
    hangarllm.logging_callback_manager.add_hangarllm_callback(_lasso_callback)

    return _lasso_callback


guardrail_initializer_registry: Final = {
    SupportedGuardrailIntegrations.LASSO.value: initialize_guardrail,
}


guardrail_class_registry: Final = {
    SupportedGuardrailIntegrations.LASSO.value: LassoGuardrail,
}
