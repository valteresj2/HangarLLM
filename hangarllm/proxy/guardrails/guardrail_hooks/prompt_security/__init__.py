from typing import TYPE_CHECKING, Final

from hangarllm.types.guardrails import SupportedGuardrailIntegrations

from .prompt_security import PromptSecurityGuardrail

if TYPE_CHECKING:
    from hangarllm.types.guardrails import Guardrail, HangarllmParams


def initialize_guardrail(hangarllm_params: "HangarllmParams", guardrail: "Guardrail"):
    import hangarllm
    from hangarllm.proxy.guardrails.guardrail_hooks.prompt_security import (
        PromptSecurityGuardrail,
    )

    _prompt_security_callback: Final = PromptSecurityGuardrail(
        api_base=hangarllm_params.api_base,
        api_key=hangarllm_params.api_key,
        guardrail_name=guardrail.get("guardrail_name", ""),
        event_hook=hangarllm_params.mode,
        default_on=hangarllm_params.default_on,
        streaming_transform_mode=getattr(hangarllm_params, "streaming_transform_mode", None),
        file_sanitization_fail_open=getattr(hangarllm_params, "file_sanitization_fail_open", None),
        block_on_file_modify=getattr(hangarllm_params, "block_on_file_modify", None),
        timeout=hangarllm_params.timeout,
    )
    hangarllm.logging_callback_manager.add_hangarllm_callback(_prompt_security_callback)

    return _prompt_security_callback


guardrail_initializer_registry: Final = {
    SupportedGuardrailIntegrations.PROMPT_SECURITY.value: initialize_guardrail,
}


guardrail_class_registry: Final = {
    SupportedGuardrailIntegrations.PROMPT_SECURITY.value: PromptSecurityGuardrail,
}
