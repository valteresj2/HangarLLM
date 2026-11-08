"""Cisco AI Defense Guardrail Integration for HangarLLM."""

from typing import TYPE_CHECKING, Final

from hangarllm.types.guardrails import SupportedGuardrailIntegrations

from .cisco_ai_defense import (
    CiscoAIDefenseGuardrail,
    CiscoAIDefenseGuardrailAPIError,
    CiscoAIDefenseGuardrailMissingSecrets,
)

if TYPE_CHECKING:
    from hangarllm.types.guardrails import Guardrail, HangarllmParams


def initialize_guardrail(hangarllm_params: "HangarllmParams", guardrail: "Guardrail"):
    import hangarllm

    guardrail_name: Final = guardrail.get("guardrail_name")
    if not guardrail_name:
        raise ValueError("Cisco AI Defense: guardrail_name is required")

    optional_params: Final = getattr(hangarllm_params, "optional_params", None)

    _callback: Final = CiscoAIDefenseGuardrail(
        guardrail_name=guardrail_name,
        api_key=hangarllm_params.api_key,
        api_base=hangarllm_params.api_base,
        inspection_type=_get_optional_value(hangarllm_params, optional_params, "inspection_type"),
        inspect_path=_get_optional_value(hangarllm_params, optional_params, "inspect_path"),
        enabled_rules=_get_optional_value(hangarllm_params, optional_params, "enabled_rules"),
        integration_profile_id=_get_optional_value(hangarllm_params, optional_params, "integration_profile_id"),
        integration_profile_version=_get_optional_value(hangarllm_params, optional_params, "integration_profile_version"),
        integration_tenant_id=_get_optional_value(hangarllm_params, optional_params, "integration_tenant_id"),
        integration_type=_get_optional_value(hangarllm_params, optional_params, "integration_type"),
        on_flagged_action=_get_optional_value(hangarllm_params, optional_params, "on_flagged_action"),
        fallback_on_error=_get_optional_value(hangarllm_params, optional_params, "fallback_on_error"),
        timeout=_get_optional_value(hangarllm_params, optional_params, "timeout"),
        event_hook=hangarllm_params.mode,
        default_on=hangarllm_params.default_on or False,
    )
    hangarllm.logging_callback_manager.add_hangarllm_callback(_callback)

    # MCP post-tool-call hooks are dispatched through success callbacks.
    hangarllm.logging_callback_manager.add_hangarllm_success_callback(_callback)

    return _callback


def _get_optional_value(hangarllm_params, optional_params, attribute_name):
    """Resolve Cisco optional params without inheriting sibling defaults."""
    if optional_params is not None:
        if isinstance(optional_params, dict):
            if attribute_name in optional_params:
                return optional_params[attribute_name]
        else:
            nested_fields_set: Final = getattr(optional_params, "model_fields_set", None)
            if nested_fields_set is None or attribute_name in nested_fields_set:
                value: Final = getattr(optional_params, attribute_name, None)
                if value is not None:
                    return value

    if hangarllm_params is None:
        return None
    # Only accept flattened values the caller explicitly set.
    fields_set: Final = getattr(hangarllm_params, "model_fields_set", None)
    if fields_set is None or attribute_name not in fields_set:
        return None
    return getattr(hangarllm_params, attribute_name, None)


guardrail_initializer_registry: Final = {
    SupportedGuardrailIntegrations.CISCO_AI_DEFENSE.value: initialize_guardrail,
}


guardrail_class_registry: Final = {
    SupportedGuardrailIntegrations.CISCO_AI_DEFENSE.value: CiscoAIDefenseGuardrail,
}


__all__ = [
    "CiscoAIDefenseGuardrail",
    "CiscoAIDefenseGuardrailAPIError",
    "CiscoAIDefenseGuardrailMissingSecrets",
    "guardrail_class_registry",
    "guardrail_initializer_registry",
    "initialize_guardrail",
]
