from typing import TYPE_CHECKING, Final

from hangarllm.types.guardrails import SupportedGuardrailIntegrations

from .pangea import PangeaHandler

if TYPE_CHECKING:
    from hangarllm.types.guardrails import Guardrail, HangarllmParams


def initialize_guardrail(hangarllm_params: "HangarllmParams", guardrail: "Guardrail"):
    import hangarllm

    guardrail_name: Final = guardrail.get("guardrail_name")
    if not guardrail_name:
        raise ValueError("Pangea guardrail name is required")

    _pangea_callback: Final = PangeaHandler(
        guardrail_name=guardrail_name,
        pangea_input_recipe=hangarllm_params.pangea_input_recipe,
        pangea_output_recipe=hangarllm_params.pangea_output_recipe,
        api_base=hangarllm_params.api_base,
        api_key=hangarllm_params.api_key,
        event_hook=hangarllm_params.mode,
        default_on=hangarllm_params.default_on,
        timeout=hangarllm_params.timeout,
    )
    hangarllm.logging_callback_manager.add_hangarllm_callback(_pangea_callback)

    return _pangea_callback


guardrail_initializer_registry: Final = {
    SupportedGuardrailIntegrations.PANGEA.value: initialize_guardrail,
}


guardrail_class_registry: Final = {
    SupportedGuardrailIntegrations.PANGEA.value: PangeaHandler,
}
