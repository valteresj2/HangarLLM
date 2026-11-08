from typing import TYPE_CHECKING, Final

from hangarllm.types.guardrails import SupportedGuardrailIntegrations

from .akto import AktoGuardrail, streaming_sampling_rate_from

if TYPE_CHECKING:
    from hangarllm.types.guardrails import Guardrail, HangarllmParams


def initialize_guardrail(hangarllm_params: "HangarllmParams", guardrail: "Guardrail"):
    import hangarllm

    _akto_callback: Final = AktoGuardrail(
        akto_base_url=hangarllm_params.akto_base_url,
        akto_api_key=hangarllm_params.akto_api_key,
        akto_account_id=hangarllm_params.akto_account_id,
        akto_vxlan_id=hangarllm_params.akto_vxlan_id,
        context_source=hangarllm_params.context_source,
        akto_metadata=hangarllm_params.akto_metadata,
        streaming_sampling_rate=streaming_sampling_rate_from(hangarllm_params),
        guardrail_timeout=hangarllm_params.guardrail_timeout,
        file_guardrail_timeout=hangarllm_params.file_guardrail_timeout,
        unreachable_fallback=hangarllm_params.unreachable_fallback,
        guardrail_name=guardrail.get("guardrail_name", ""),
        event_hook=hangarllm_params.mode,
        default_on=hangarllm_params.default_on,
    )

    hangarllm.logging_callback_manager.add_hangarllm_callback(_akto_callback)
    return _akto_callback


guardrail_initializer_registry: Final = {
    SupportedGuardrailIntegrations.AKTO.value: initialize_guardrail,
}

guardrail_class_registry: Final = {
    SupportedGuardrailIntegrations.AKTO.value: AktoGuardrail,
}
