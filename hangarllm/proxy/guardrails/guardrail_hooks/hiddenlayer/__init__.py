from typing import TYPE_CHECKING, Final

from hangarllm.types.guardrails import SupportedGuardrailIntegrations

from .hiddenlayer import HiddenlayerGuardrail, HiddenlayerGuardrailV2

if TYPE_CHECKING:
    from hangarllm.types.guardrails import Guardrail, HangarllmParams


def initialize_guardrail(hangarllm_params: "HangarllmParams", guardrail: "Guardrail"):
    import hangarllm

    api_id: Final = hangarllm_params.api_id if hasattr(hangarllm_params, "api_id") else None
    auth_url: Final = hangarllm_params.auth_url if hasattr(hangarllm_params, "auth_url") else None
    version: Final[int | None] = hangarllm_params.version if hasattr(hangarllm_params, "version") else None

    _hiddenlayer_callback: HiddenlayerGuardrail | HiddenlayerGuardrailV2
    if not version or version < 2:
        _hiddenlayer_callback = HiddenlayerGuardrail(
            api_base=hangarllm_params.api_base,
            api_id=api_id,
            api_key=hangarllm_params.api_key,
            auth_url=auth_url,
            guardrail_name=guardrail.get("guardrail_name", ""),
            event_hook=hangarllm_params.mode,
            default_on=hangarllm_params.default_on,
            timeout=hangarllm_params.timeout,
        )
    else:
        _hiddenlayer_callback = HiddenlayerGuardrailV2(
            api_base=hangarllm_params.api_base,
            api_id=api_id,
            api_key=hangarllm_params.api_key,
            auth_url=auth_url,
            guardrail_name=guardrail.get("guardrail_name", ""),
            event_hook=hangarllm_params.mode,
            default_on=hangarllm_params.default_on,
            timeout=hangarllm_params.timeout,
        )

    hangarllm.logging_callback_manager.add_hangarllm_callback(_hiddenlayer_callback)
    return _hiddenlayer_callback


guardrail_initializer_registry: Final = {
    SupportedGuardrailIntegrations.HIDDENLAYER.value: initialize_guardrail,
}


guardrail_class_registry: Final = {
    SupportedGuardrailIntegrations.HIDDENLAYER.value: HiddenlayerGuardrail,
}
