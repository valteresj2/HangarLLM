from typing import TYPE_CHECKING, Final

from hangarllm.types.guardrails import SupportedGuardrailIntegrations

from .singulr import SingulrGuardrail

if TYPE_CHECKING:
    from hangarllm.types.guardrails import Guardrail, HangarllmParams


def initialize_guardrail(
    hangarllm_params: "HangarllmParams",
    guardrail: "Guardrail",
):
    import hangarllm

    _cb: Final = SingulrGuardrail(
        singulr_api_base=getattr(hangarllm_params, "singulr_api_base", None) or hangarllm_params.api_base,
        singulr_api_key=getattr(hangarllm_params, "singulr_api_key", None) or hangarllm_params.api_key,
        singulr_application_id=getattr(hangarllm_params, "singulr_application_id", None),
        singulr_guardrail_id=getattr(hangarllm_params, "singulr_guardrail_id", None),
        block_on_error=getattr(hangarllm_params, "block_on_error", None),
        timeout=hangarllm_params.timeout,
        guardrail_name=guardrail.get(
            "guardrail_name",
            "",
        ),
        event_hook=hangarllm_params.mode,
        default_on=hangarllm_params.default_on,
    )
    hangarllm.logging_callback_manager.add_hangarllm_callback(
        _cb,
    )

    return _cb


guardrail_initializer_registry: Final = {
    SupportedGuardrailIntegrations.SINGULR.value: initialize_guardrail,
}

guardrail_class_registry: Final = {
    SupportedGuardrailIntegrations.SINGULR.value: SingulrGuardrail,
}
