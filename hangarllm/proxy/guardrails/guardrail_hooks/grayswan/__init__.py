"""Gray Swan Cygnal guardrail integration for HangarLLM."""

from typing import TYPE_CHECKING, Final

from hangarllm.types.guardrails import SupportedGuardrailIntegrations

from .grayswan import (
    GraySwanGuardrail,
    GraySwanGuardrailAPIError,
    GraySwanGuardrailMissingSecrets,
)

if TYPE_CHECKING:
    from hangarllm.types.guardrails import Guardrail, HangarllmParams


def initialize_guardrail(hangarllm_params: "HangarllmParams", guardrail: "Guardrail") -> GraySwanGuardrail:
    import hangarllm

    guardrail_name: Final = guardrail.get("guardrail_name")
    if not guardrail_name:
        raise ValueError("Gray Swan guardrail requires a guardrail_name")

    optional_params: Final = getattr(hangarllm_params, "optional_params", None)

    grayswan_guardrail: Final = GraySwanGuardrail(
        guardrail_name=guardrail_name,
        api_key=hangarllm_params.api_key,
        api_base=hangarllm_params.api_base,
        on_flagged_action=_get_config_value(hangarllm_params, optional_params, "on_flagged_action"),
        violation_threshold=_get_config_value(hangarllm_params, optional_params, "violation_threshold"),
        reasoning_mode=_get_config_value(hangarllm_params, optional_params, "reasoning_mode"),
        categories=_get_config_value(hangarllm_params, optional_params, "categories"),
        policy_id=_get_config_value(hangarllm_params, optional_params, "policy_id"),
        streaming_end_of_stream_only=_get_config_value(hangarllm_params, optional_params, "streaming_end_of_stream_only")
        or False,
        streaming_sampling_rate=_get_config_value(hangarllm_params, optional_params, "streaming_sampling_rate") or 5,
        fail_open=_get_config_value(hangarllm_params, optional_params, "fail_open"),
        guardrail_timeout=_get_config_value(hangarllm_params, optional_params, "guardrail_timeout"),
        event_hook=hangarllm_params.mode,
        default_on=hangarllm_params.default_on,
    )

    hangarllm.logging_callback_manager.add_hangarllm_callback(grayswan_guardrail)
    return grayswan_guardrail


def _get_config_value(hangarllm_params, optional_params, attribute_name):
    if optional_params is not None:
        value: Final = getattr(optional_params, attribute_name, None)
        if value is not None:
            return value
    return getattr(hangarllm_params, attribute_name, None)


guardrail_initializer_registry: Final = {
    SupportedGuardrailIntegrations.GRAYSWAN.value: initialize_guardrail,
}


guardrail_class_registry: Final = {
    SupportedGuardrailIntegrations.GRAYSWAN.value: GraySwanGuardrail,
}


__all__ = [
    "GraySwanGuardrail",
    "GraySwanGuardrailAPIError",
    "GraySwanGuardrailMissingSecrets",
    "initialize_guardrail",
]
