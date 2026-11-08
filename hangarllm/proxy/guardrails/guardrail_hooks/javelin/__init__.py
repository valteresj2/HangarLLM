from typing import TYPE_CHECKING, Final

from hangarllm.types.guardrails import SupportedGuardrailIntegrations

from .javelin import JavelinGuardrail

if TYPE_CHECKING:
    from hangarllm.types.guardrails import Guardrail, HangarllmParams


def initialize_guardrail(hangarllm_params: "HangarllmParams", guardrail: "Guardrail"):
    import hangarllm

    if hangarllm_params.guard_name is None:
        raise Exception(
            "JavelinGuardrailException - Please pass the Javelin guard name via 'hangarllm_params::guard_name'"
        )

    _javelin_callback: Final = JavelinGuardrail(
        api_base=hangarllm_params.api_base,
        api_key=hangarllm_params.api_key,
        guardrail_name=guardrail.get("guardrail_name", ""),
        javelin_guard_name=hangarllm_params.guard_name,
        event_hook=hangarllm_params.mode,
        default_on=hangarllm_params.default_on or False,
        api_version=hangarllm_params.api_version or "v1",
        config=hangarllm_params.config,
        metadata=hangarllm_params.metadata,
        application=hangarllm_params.application,
        timeout=hangarllm_params.timeout,
    )
    hangarllm.logging_callback_manager.add_hangarllm_callback(_javelin_callback)

    return _javelin_callback


guardrail_initializer_registry: Final = {
    SupportedGuardrailIntegrations.JAVELIN.value: initialize_guardrail,
}


guardrail_class_registry: Final = {
    SupportedGuardrailIntegrations.JAVELIN.value: JavelinGuardrail,
}
