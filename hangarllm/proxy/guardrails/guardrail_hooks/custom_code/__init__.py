"""Custom code guardrail integration for HangarLLM.

This module allows users to write custom guardrail logic using Python-like code
that runs in a sandboxed environment with access to HangarLLM-provided primitives.

Pre-built custom code for common guardrails (e.g. response rejection detection)
is available in response_rejection_code.py.
"""

from typing import TYPE_CHECKING, Final

from hangarllm.types.guardrails import SupportedGuardrailIntegrations

from .custom_code_guardrail import CustomCodeGuardrail
from .response_rejection_code import (
    DEFAULT_REJECTION_PHRASES,
    RESPONSE_REJECTION_GUARDRAIL_CODE,
)

if TYPE_CHECKING:
    from hangarllm.types.guardrails import Guardrail, HangarllmParams


def initialize_guardrail(hangarllm_params: "HangarllmParams", guardrail: "Guardrail") -> CustomCodeGuardrail:
    """
    Initialize a custom code guardrail.

    Args:
        hangarllm_params: Configuration parameters including the custom code
        guardrail: The guardrail configuration dict

    Returns:
        CustomCodeGuardrail instance
    """
    import hangarllm

    guardrail_name: Final = guardrail.get("guardrail_name")
    if not guardrail_name:
        raise ValueError("Custom code guardrail requires a guardrail_name")

    # Get the custom code from hangarllm_params
    custom_code: Final = hangarllm_params.custom_code
    if not custom_code:
        raise ValueError("Custom code guardrail requires 'custom_code' in hangarllm_params")

    custom_code_guardrail: Final = CustomCodeGuardrail(
        guardrail_name=guardrail_name,
        custom_code=custom_code,
        execution_timeout=hangarllm_params.timeout,
        event_hook=hangarllm_params.mode,
        default_on=hangarllm_params.default_on,
    )

    hangarllm.logging_callback_manager.add_hangarllm_callback(custom_code_guardrail)
    return custom_code_guardrail


guardrail_initializer_registry: Final = {
    SupportedGuardrailIntegrations.CUSTOM_CODE.value: initialize_guardrail,
}

guardrail_class_registry: Final = {
    SupportedGuardrailIntegrations.CUSTOM_CODE.value: CustomCodeGuardrail,
}

__all__ = [
    "DEFAULT_REJECTION_PHRASES",
    "RESPONSE_REJECTION_GUARDRAIL_CODE",
    "CustomCodeGuardrail",
    "initialize_guardrail",
]
