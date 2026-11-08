from typing import TYPE_CHECKING, Final

import hangarllm
from hangarllm.hangarllm_core_utils.core_helpers import attribute_or_none
from hangarllm.proxy.guardrails.guardrail_hooks.openai.moderations import (
    OpenAIModerationGuardrail,
)
from hangarllm.types.guardrails import SupportedGuardrailIntegrations
from hangarllm.types.workload_identity import OPENAI_WIF_KWARGS_KEYS

if TYPE_CHECKING:
    from hangarllm.types.guardrails import Guardrail, HangarllmParams


def initialize_guardrail(hangarllm_params: "HangarllmParams", guardrail: "Guardrail"):
    guardrail_name: Final = guardrail.get("guardrail_name")
    if not guardrail_name:
        raise ValueError("OpenAI Moderation: guardrail_name is required")

    optional_params: Final = getattr(hangarllm_params, "optional_params", None)

    openai_moderation_guardrail: Final = OpenAIModerationGuardrail(
        guardrail_name=guardrail_name,
        workload_identity_params=hangarllm_params.model_dump(include=set(OPENAI_WIF_KWARGS_KEYS), exclude_none=True),
        **{
            **hangarllm_params.model_dump(exclude_none=True),
            "api_key": hangarllm_params.api_key,
            "api_base": hangarllm_params.api_base,
            "default_on": hangarllm_params.default_on,
            "event_hook": hangarllm_params.mode,
            "model": hangarllm_params.model,
            "streaming_end_of_stream_only": _get_config_value(
                hangarllm_params, optional_params, "streaming_end_of_stream_only"
            ),
            "streaming_sampling_rate": _get_config_value(hangarllm_params, optional_params, "streaming_sampling_rate"),
        },
    )

    hangarllm.logging_callback_manager.add_hangarllm_callback(openai_moderation_guardrail)

    return openai_moderation_guardrail


def _get_config_value(hangarllm_params: object, optional_params: object, attribute_name: str) -> object:
    if optional_params is not None:
        value: Final = attribute_or_none(optional_params, attribute_name)
        if value is not None:
            return value
    return attribute_or_none(hangarllm_params, attribute_name)


guardrail_initializer_registry: Final = {
    SupportedGuardrailIntegrations.OPENAI_MODERATION.value: initialize_guardrail,
}


guardrail_class_registry: Final = {
    SupportedGuardrailIntegrations.OPENAI_MODERATION.value: OpenAIModerationGuardrail,
}
