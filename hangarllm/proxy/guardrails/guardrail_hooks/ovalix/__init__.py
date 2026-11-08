"""Ovalix guardrail hook: registration and initialization for the proxy."""

from typing import TYPE_CHECKING, Final

from hangarllm.types.guardrails import SupportedGuardrailIntegrations

from .ovalix import OvalixGuardrail

if TYPE_CHECKING:
    from hangarllm.types.guardrails import Guardrail, HangarllmParams


def initialize_guardrail(hangarllm_params: "HangarllmParams", guardrail: "Guardrail"):
    """Create and register an Ovalix guardrail callback from proxy config."""
    import hangarllm

    tracker_api_base: Final = getattr(hangarllm_params, "tracker_api_base", None)
    tracker_api_key: Final = getattr(hangarllm_params, "tracker_api_key", None)
    application_id: Final = getattr(hangarllm_params, "application_id", None)
    pre_checkpoint_id: Final = getattr(hangarllm_params, "pre_checkpoint_id", None)
    post_checkpoint_id: Final = getattr(hangarllm_params, "post_checkpoint_id", None)
    file_checkpoint_id: Final = getattr(hangarllm_params, "file_checkpoint_id", None)

    _ovalix_callback: Final = OvalixGuardrail(
        guardrail_name=guardrail.get("guardrail_name", ""),
        tracker_api_base=tracker_api_base,
        tracker_api_key=tracker_api_key,
        application_id=application_id,
        pre_checkpoint_id=pre_checkpoint_id,
        post_checkpoint_id=post_checkpoint_id,
        file_checkpoint_id=file_checkpoint_id,
        event_hook=hangarllm_params.mode,
        default_on=hangarllm_params.default_on,
        timeout=hangarllm_params.timeout,
    )
    hangarllm.logging_callback_manager.add_hangarllm_callback(_ovalix_callback)

    return _ovalix_callback


# Registry of guardrail name -> initializer for proxy config loading.
guardrail_initializer_registry: Final = {
    SupportedGuardrailIntegrations.OVALIX.value: initialize_guardrail,
}

# Registry of guardrail name -> guardrail class (e.g. for apply_guardrail API).
guardrail_class_registry: Final = {
    SupportedGuardrailIntegrations.OVALIX.value: OvalixGuardrail,
}
