from __future__ import annotations

from typing import TYPE_CHECKING, Final

from hangarllm.hangarllm_core_utils.core_helpers import attribute_or_none
from hangarllm.types.guardrails import (
    GuardrailEventHooks,
    Mode,
    SupportedGuardrailIntegrations,
)

from .compresr import CompresrGuardrail

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


def _get_optional_value(hangarllm_params: HangarllmParams, optional_params: object | None, attribute_name: str) -> object:
    if optional_params is not None:
        value: Final = attribute_or_none(optional_params, attribute_name)
        if value is not None:
            return value
    return getattr(hangarllm_params, attribute_name, None)


def initialize_guardrail(hangarllm_params: HangarllmParams, guardrail: Guardrail) -> CompresrGuardrail:
    import hangarllm

    optional_params: Final = getattr(hangarllm_params, "optional_params", None)

    _callback: Final = CompresrGuardrail(
        api_base=hangarllm_params.api_base,
        api_key=hangarllm_params.api_key,
        model=hangarllm_params.model,
        target_compression_ratio=_get_optional_value(hangarllm_params, optional_params, "target_compression_ratio"),
        coarse=_get_optional_value(hangarllm_params, optional_params, "coarse"),
        min_chars_to_compress=_get_optional_value(hangarllm_params, optional_params, "min_chars_to_compress"),
        compress_tool_outputs=_get_optional_value(hangarllm_params, optional_params, "compress_tool_outputs"),
        compress_system=_get_optional_value(hangarllm_params, optional_params, "compress_system"),
        compress_history=_get_optional_value(hangarllm_params, optional_params, "compress_history"),
        compress_last_user=_get_optional_value(hangarllm_params, optional_params, "compress_last_user"),
        enable_retrieval=_get_optional_value(hangarllm_params, optional_params, "enable_retrieval"),
        max_bytes_per_call=_get_optional_value(hangarllm_params, optional_params, "max_bytes_per_call"),
        allow_bypass_header=_get_optional_value(hangarllm_params, optional_params, "allow_bypass_header"),
        dynamic=_get_optional_value(hangarllm_params, optional_params, "dynamic"),
        dynamic_min_ratio=_get_optional_value(hangarllm_params, optional_params, "dynamic_min_ratio"),
        dynamic_max_ratio=_get_optional_value(hangarllm_params, optional_params, "dynamic_max_ratio"),
        compression_params=_get_optional_value(hangarllm_params, optional_params, "compression_params"),
        guardrail_name=guardrail["guardrail_name"],
        event_hook=_coerce_event_hook(hangarllm_params.mode),
        default_on=hangarllm_params.default_on or False,
        unreachable_fallback=hangarllm_params.unreachable_fallback,
        timeout=hangarllm_params.timeout,
    )
    hangarllm.logging_callback_manager.add_hangarllm_callback(  # pyright: ignore[reportUnknownMemberType]  # callback manager is untyped
        _callback
    )
    return _callback


guardrail_initializer_registry: Final = {
    SupportedGuardrailIntegrations.COMPRESR.value: initialize_guardrail,
}

guardrail_class_registry: Final = {
    SupportedGuardrailIntegrations.COMPRESR.value: CompresrGuardrail,
}
