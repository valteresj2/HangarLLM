from typing import TYPE_CHECKING, Final

from hangarllm.types.guardrails import (
    GuardrailEventHooks,
    Mode,
    SupportedGuardrailIntegrations,
)

from .repelloai import RepelloAIGuardrail

if TYPE_CHECKING:
    from hangarllm.types.guardrails import Guardrail, HangarllmParams


def _event_hook_from_mode(
    mode: str | list[str] | Mode,
) -> GuardrailEventHooks | list[GuardrailEventHooks] | Mode:
    if isinstance(mode, Mode):
        return mode
    if isinstance(mode, list):
        return [GuardrailEventHooks(item) for item in mode]
    return GuardrailEventHooks(mode)


def initialize_guardrail(hangarllm_params: "HangarllmParams", guardrail: "Guardrail") -> RepelloAIGuardrail:
    import hangarllm

    _repelloai_callback: Final = RepelloAIGuardrail(
        guardrail_name=guardrail["guardrail_name"],
        api_key=hangarllm_params.api_key,
        api_base=hangarllm_params.api_base,
        asset_id=hangarllm_params.asset_id,
        unreachable_fallback=hangarllm_params.unreachable_fallback,
        event_hook=_event_hook_from_mode(hangarllm_params.mode),
        default_on=hangarllm_params.default_on or False,
        timeout=hangarllm_params.timeout,
    )
    hangarllm.logging_callback_manager.add_hangarllm_callback(_repelloai_callback)

    return _repelloai_callback


guardrail_initializer_registry: Final = {
    SupportedGuardrailIntegrations.REPELLOAI.value: initialize_guardrail,
}


guardrail_class_registry: Final = {
    SupportedGuardrailIntegrations.REPELLOAI.value: RepelloAIGuardrail,
}
