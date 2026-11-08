from typing import TYPE_CHECKING, Final

from hangarllm.types.guardrails import SupportedGuardrailIntegrations

from .model_armor import ModelArmorGuardrail

if TYPE_CHECKING:
    from hangarllm.types.guardrails import Guardrail, HangarllmParams


def initialize_guardrail(hangarllm_params: "HangarllmParams", guardrail: "Guardrail"):
    import hangarllm
    from hangarllm.proxy.guardrails.guardrail_hooks.model_armor import (
        ModelArmorGuardrail,
    )

    _model_armor_callback: Final = ModelArmorGuardrail(
        guardrail_name=guardrail.get("guardrail_name", ""),
        event_hook=hangarllm_params.mode,
        template_id=hangarllm_params.template_id,
        project_id=hangarllm_params.project_id,
        location=hangarllm_params.location,
        credentials=hangarllm_params.credentials,
        api_endpoint=hangarllm_params.api_endpoint,
        default_on=hangarllm_params.default_on,
        mask_request_content=hangarllm_params.mask_request_content,
        mask_response_content=hangarllm_params.mask_response_content,
        fail_on_error=hangarllm_params.fail_on_error,
        skip_unscannable_attachments=hangarllm_params.skip_unscannable_attachments,
        sanitize_error_detail=hangarllm_params.sanitize_error_detail,
        timeout=hangarllm_params.timeout,
    )
    hangarllm.logging_callback_manager.add_hangarllm_callback(_model_armor_callback)

    return _model_armor_callback


guardrail_initializer_registry: Final = {
    SupportedGuardrailIntegrations.MODEL_ARMOR.value: initialize_guardrail,
}


guardrail_class_registry: Final = {
    SupportedGuardrailIntegrations.MODEL_ARMOR.value: ModelArmorGuardrail,
}
