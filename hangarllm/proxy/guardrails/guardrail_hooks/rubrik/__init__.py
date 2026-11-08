"""Rubrik guardrail integration for HangarLLM."""

from typing import TYPE_CHECKING, Final

from hangarllm.integrations.rubrik import RubrikLogger
from hangarllm.types.guardrails import SupportedGuardrailIntegrations

if TYPE_CHECKING:
    from hangarllm.types.guardrails import Guardrail, HangarllmParams


def initialize_guardrail(hangarllm_params: "HangarllmParams", guardrail: "Guardrail") -> RubrikLogger:
    """Create and register a RubrikLogger instance.

    The ``mode`` field in the guardrail config controls which surfaces are
    moderated:
    - ``pre_call`` (or a mode that includes it): prompt moderation via the
      ``/v1/before_prompt/openai/v1`` webhook.
    - ``post_call`` (the default when ``mode`` is omitted): response and tool
      call moderation via the ``/v1/after_completion/openai/v1`` webhook.

    Both hooks are active when ``mode`` covers both ``pre_call`` and
    ``post_call``.
    """
    import hangarllm

    rubrik_callback: Final = RubrikLogger(
        api_key=hangarllm_params.api_key,
        api_base=hangarllm_params.api_base,
        guardrail_name=guardrail.get("guardrail_name", ""),
        event_hook=hangarllm_params.mode,
        default_on=hangarllm_params.default_on,
        timeout=hangarllm_params.timeout,
    )

    hangarllm.logging_callback_manager.add_hangarllm_callback(rubrik_callback)
    return rubrik_callback


guardrail_initializer_registry: Final = {
    SupportedGuardrailIntegrations.RUBRIK.value: initialize_guardrail,
}

guardrail_class_registry: Final = {
    SupportedGuardrailIntegrations.RUBRIK.value: RubrikLogger,
}
