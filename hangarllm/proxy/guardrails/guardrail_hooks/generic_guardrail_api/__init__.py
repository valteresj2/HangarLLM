from typing import TYPE_CHECKING, Any, Final

from hangarllm.types.guardrails import SupportedGuardrailIntegrations

from .generic_guardrail_api import GenericGuardrailAPI

if TYPE_CHECKING:
    from hangarllm.types.guardrails import Guardrail, HangarllmParams


def _get_config_value(hangarllm_params: "HangarllmParams", optional_params: object, attribute_name: str) -> Any | None:
    if optional_params is not None:
        value: Final = (
            optional_params.get(attribute_name)
            if isinstance(optional_params, dict)
            else getattr(optional_params, attribute_name, None)
        )
        if value is not None:
            return value
    return getattr(hangarllm_params, attribute_name, None)


def initialize_guardrail(hangarllm_params: "HangarllmParams", guardrail: "Guardrail"):
    import hangarllm

    optional_params: Final = getattr(hangarllm_params, "optional_params", None)

    _generic_guardrail_api_callback: Final = GenericGuardrailAPI(
        api_base=hangarllm_params.api_base,
        api_key=hangarllm_params.api_key,
        headers=getattr(hangarllm_params, "headers", None),
        additional_provider_specific_params=getattr(hangarllm_params, "additional_provider_specific_params", {}),
        unreachable_fallback=getattr(hangarllm_params, "unreachable_fallback", "fail_closed"),
        fail_on_error=getattr(hangarllm_params, "fail_on_error", True),
        forward_messages_as_sent=hangarllm_params.forward_messages_as_sent,
        extra_headers=getattr(hangarllm_params, "extra_headers", None),
        guardrail_name=guardrail.get("guardrail_name", ""),
        event_hook=hangarllm_params.mode,
        default_on=hangarllm_params.default_on,
        streaming_end_of_stream_only=_get_config_value(hangarllm_params, optional_params, "streaming_end_of_stream_only"),
        streaming_sampling_rate=_get_config_value(hangarllm_params, optional_params, "streaming_sampling_rate"),
        streaming_transform_mode=_get_config_value(hangarllm_params, optional_params, "streaming_transform_mode"),
        streaming_buffer_until_moderated=_get_config_value(
            hangarllm_params, optional_params, "streaming_buffer_until_moderated"
        ),
        timeout=hangarllm_params.timeout,
        num_retries=hangarllm_params.num_retries,
    )

    hangarllm.logging_callback_manager.add_hangarllm_callback(_generic_guardrail_api_callback)
    return _generic_guardrail_api_callback


guardrail_initializer_registry: Final = {
    SupportedGuardrailIntegrations.GENERIC_GUARDRAIL_API.value: initialize_guardrail,
}

guardrail_class_registry: Final = {
    SupportedGuardrailIntegrations.GENERIC_GUARDRAIL_API.value: GenericGuardrailAPI,
}
