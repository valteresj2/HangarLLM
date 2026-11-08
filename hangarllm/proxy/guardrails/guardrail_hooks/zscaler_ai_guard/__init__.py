from typing import TYPE_CHECKING, Final

from hangarllm.types.guardrails import SupportedGuardrailIntegrations

from .zscaler_ai_guard import ZscalerAIGuard

if TYPE_CHECKING:
    from hangarllm.types.guardrails import Guardrail, HangarllmParams


def initialize_guardrail(hangarllm_params: "HangarllmParams", guardrail: "Guardrail"):
    import hangarllm

    _zscaler_ai_guard_callback: Final = ZscalerAIGuard(
        api_base=hangarllm_params.api_base,
        api_key=hangarllm_params.api_key,
        policy_id=hangarllm_params.policy_id,
        send_user_api_key_alias=hangarllm_params.send_user_api_key_alias,
        send_user_api_key_user_id=hangarllm_params.send_user_api_key_user_id,
        send_user_api_key_team_id=hangarllm_params.send_user_api_key_team_id,
        timeout=hangarllm_params.timeout,
        guardrail_name=guardrail.get("guardrail_name", ""),
        event_hook=hangarllm_params.mode,
        default_on=hangarllm_params.default_on,
    )
    hangarllm.logging_callback_manager.add_hangarllm_callback(_zscaler_ai_guard_callback)

    return _zscaler_ai_guard_callback


guardrail_initializer_registry: Final = {
    SupportedGuardrailIntegrations.ZSCALER_AI_GUARD.value: initialize_guardrail,
}


guardrail_class_registry: Final = {
    SupportedGuardrailIntegrations.ZSCALER_AI_GUARD.value: ZscalerAIGuard,
}
