from typing import TYPE_CHECKING, Final

from hangarllm.types.guardrails import SupportedGuardrailIntegrations

from .noma import NomaGuardrail
from .noma_v2 import NomaV2Guardrail

if TYPE_CHECKING:
    from hangarllm.types.guardrails import Guardrail, HangarllmParams


def initialize_guardrail(hangarllm_params: "HangarllmParams", guardrail: "Guardrail"):
    use_v2 = getattr(hangarllm_params, "use_v2", False)
    if isinstance(use_v2, str):
        use_v2 = use_v2.lower() == "true"
    if use_v2:
        return initialize_guardrail_v2(hangarllm_params=hangarllm_params, guardrail=guardrail)

    import hangarllm

    _noma_callback: Final = NomaGuardrail(
        guardrail_name=guardrail.get("guardrail_name", ""),
        api_key=hangarllm_params.api_key,
        api_base=hangarllm_params.api_base,
        application_id=hangarllm_params.application_id,
        monitor_mode=hangarllm_params.monitor_mode,
        block_failures=hangarllm_params.block_failures,
        anonymize_input=hangarllm_params.anonymize_input,
        event_hook=hangarllm_params.mode,
        default_on=hangarllm_params.default_on,
        timeout=hangarllm_params.timeout,
    )
    hangarllm.logging_callback_manager.add_hangarllm_callback(_noma_callback)

    return _noma_callback


def initialize_guardrail_v2(hangarllm_params: "HangarllmParams", guardrail: "Guardrail"):
    import hangarllm

    extras: Final = hangarllm_params.model_extra or {}
    _noma_v2_callback: Final = NomaV2Guardrail(
        guardrail_name=guardrail.get("guardrail_name", ""),
        api_key=hangarllm_params.api_key,
        api_base=hangarllm_params.api_base,
        application_id=hangarllm_params.application_id,
        gateway_name=hangarllm_params.gateway_name,
        monitor_mode=hangarllm_params.monitor_mode,
        block_failures=hangarllm_params.block_failures,
        event_hook=hangarllm_params.mode,
        default_on=hangarllm_params.default_on,
        timeout=hangarllm_params.timeout,
        streaming_buffer_until_moderated=extras.get("streaming_buffer_until_moderated"),
        streaming_end_of_stream_only=extras.get("streaming_end_of_stream_only"),
        streaming_sampling_rate=extras.get("streaming_sampling_rate"),
        streaming_buffer_release_on_scan=extras.get("streaming_buffer_release_on_scan"),
    )
    hangarllm.logging_callback_manager.add_hangarllm_callback(_noma_v2_callback)

    return _noma_v2_callback


guardrail_initializer_registry: Final = {
    SupportedGuardrailIntegrations.NOMA.value: initialize_guardrail,
    SupportedGuardrailIntegrations.NOMA_V2.value: initialize_guardrail_v2,
}


guardrail_class_registry: Final = {
    SupportedGuardrailIntegrations.NOMA.value: NomaGuardrail,
    SupportedGuardrailIntegrations.NOMA_V2.value: NomaV2Guardrail,
}
