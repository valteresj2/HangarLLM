"""
Pillar Security Guardrail Integration for HangarLLM
"""

from typing import TYPE_CHECKING, Final

from hangarllm.types.guardrails import SupportedGuardrailIntegrations

from .pillar import (
    PillarGuardrail,
    PillarGuardrailAPIError,
    PillarGuardrailMissingSecrets,
)

if TYPE_CHECKING:
    from hangarllm.types.guardrails import Guardrail, HangarllmParams


def initialize_guardrail(hangarllm_params: "HangarllmParams", guardrail: "Guardrail"):
    import hangarllm

    guardrail_name: Final = guardrail.get("guardrail_name")
    if not guardrail_name:
        raise ValueError("Pillar guardrail name is required")

    optional_params: Final = getattr(hangarllm_params, "optional_params", None)

    _pillar_callback: Final = PillarGuardrail(
        guardrail_name=guardrail_name,
        api_key=hangarllm_params.api_key,
        api_base=hangarllm_params.api_base,
        on_flagged_action=getattr(hangarllm_params, "on_flagged_action", "monitor"),
        event_hook=hangarllm_params.mode,
        default_on=hangarllm_params.default_on,
        async_mode=_get_config_value(hangarllm_params, optional_params, "async_mode"),
        persist_session=_get_config_value(hangarllm_params, optional_params, "persist_session"),
        include_scanners=_get_config_value(hangarllm_params, optional_params, "include_scanners"),
        include_evidence=_get_config_value(hangarllm_params, optional_params, "include_evidence"),
        fallback_on_error=_get_config_value(hangarllm_params, optional_params, "fallback_on_error"),
        timeout=_get_config_value(hangarllm_params, optional_params, "timeout"),
    )
    hangarllm.logging_callback_manager.add_hangarllm_callback(_pillar_callback)

    return _pillar_callback


def _get_config_value(hangarllm_params, optional_params, attribute_name):
    """Return guardrail configuration value prioritising optional params when present."""

    if optional_params is not None:
        value: Final = getattr(optional_params, attribute_name, None)
        if value is not None:
            return value
    return getattr(hangarllm_params, attribute_name, None)


guardrail_initializer_registry: Final = {
    SupportedGuardrailIntegrations.PILLAR.value: initialize_guardrail,
}


guardrail_class_registry: Final = {
    SupportedGuardrailIntegrations.PILLAR.value: PillarGuardrail,
}

__all__ = [
    "PillarGuardrail",
    "PillarGuardrailAPIError",
    "PillarGuardrailMissingSecrets",
]
