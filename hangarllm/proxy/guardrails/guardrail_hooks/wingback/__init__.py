from __future__ import annotations

from typing import TYPE_CHECKING, Final

from hangarllm.types.guardrails import SupportedGuardrailIntegrations

from .wingback import WingbackGuardrail

if TYPE_CHECKING:
    from hangarllm.types.guardrails import Guardrail, HangarllmParams


def initialize_guardrail(
    hangarllm_params: HangarllmParams,
    guardrail: Guardrail,
) -> WingbackGuardrail:
    import hangarllm

    _wingback_callback: Final = WingbackGuardrail(
        api_base=hangarllm_params.api_base,
        api_key=hangarllm_params.api_key,
        wingback_app_id=hangarllm_params.wingback_app_id,
        additional_provider_specific_params=hangarllm_params.additional_provider_specific_params,
        unreachable_fallback=hangarllm_params.unreachable_fallback or "fail_closed",
        fail_on_error=hangarllm_params.fail_on_error,
        extra_headers=hangarllm_params.extra_headers,
        guardrail_name=guardrail["guardrail_name"],
        event_hook=hangarllm_params.mode,
        default_on=hangarllm_params.default_on,
        timeout=hangarllm_params.timeout,
    )

    hangarllm.logging_callback_manager.add_hangarllm_callback(_wingback_callback)
    return _wingback_callback


guardrail_initializer_registry: Final = {
    SupportedGuardrailIntegrations.WINGBACK.value: initialize_guardrail,
}

guardrail_class_registry: Final = {
    SupportedGuardrailIntegrations.WINGBACK.value: WingbackGuardrail,
}
