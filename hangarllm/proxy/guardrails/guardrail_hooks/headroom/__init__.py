from __future__ import annotations

from typing import TYPE_CHECKING, Final

from hangarllm.types.guardrails import (
    GuardrailEventHooks,
    Mode,
    SupportedGuardrailIntegrations,
)

from .headroom import HeadroomGuardrail

if TYPE_CHECKING:
    from hangarllm.types.guardrails import Guardrail, HangarllmParams


def _coerce_event_hook(
    mode: str | list[str] | Mode,
) -> GuardrailEventHooks | list[GuardrailEventHooks] | Mode:
    if isinstance(mode, Mode):
        return mode
    if isinstance(mode, list):
        return [GuardrailEventHooks(item) for item in mode]
    return GuardrailEventHooks(mode)


def initialize_guardrail(hangarllm_params: HangarllmParams, guardrail: Guardrail) -> HeadroomGuardrail:
    import hangarllm

    _callback: Final = HeadroomGuardrail(
        api_base=hangarllm_params.api_base,
        api_key=hangarllm_params.api_key,
        model=hangarllm_params.model,
        guardrail_name=guardrail["guardrail_name"],
        event_hook=_coerce_event_hook(hangarllm_params.mode),
        default_on=hangarllm_params.default_on or False,
        unreachable_fallback=hangarllm_params.unreachable_fallback,
        timeout=hangarllm_params.timeout,
        ccr_retrieval=hangarllm_params.ccr_retrieval,
    )
    hangarllm.logging_callback_manager.add_hangarllm_callback(  # pyright: ignore[reportUnknownMemberType]
        _callback
    )
    return _callback


guardrail_initializer_registry: Final = {
    SupportedGuardrailIntegrations.HEADROOM.value: initialize_guardrail,
}

guardrail_class_registry: Final = {
    SupportedGuardrailIntegrations.HEADROOM.value: HeadroomGuardrail,
}
