from typing import TYPE_CHECKING, Final

from hangarllm.types.guardrails import SupportedGuardrailIntegrations

from .qohash import QostodianNexus

if TYPE_CHECKING:
    from hangarllm.types.guardrails import Guardrail, HangarllmParams


def initialize_guardrail(hangarllm_params: "HangarllmParams", guardrail: "Guardrail"):
    import hangarllm

    _instance: Final = QostodianNexus(
        api_base=hangarllm_params.api_base,
        guardrail_name=guardrail.get("guardrail_name", ""),
        event_hook=hangarllm_params.mode,
        default_on=hangarllm_params.default_on,
        additional_provider_specific_params=hangarllm_params.additional_provider_specific_params,
        extra_headers=getattr(hangarllm_params, "extra_headers", None),
        timeout=hangarllm_params.timeout,
    )

    hangarllm.logging_callback_manager.add_hangarllm_callback(_instance)

    return _instance


guardrail_initializer_registry: Final = {
    SupportedGuardrailIntegrations.QOSTODIAN_NEXUS.value: initialize_guardrail,
}


guardrail_class_registry: Final = {
    SupportedGuardrailIntegrations.QOSTODIAN_NEXUS.value: QostodianNexus,
}
