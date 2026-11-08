from typing import TYPE_CHECKING, Final

from hangarllm.types.guardrails import SupportedGuardrailIntegrations

from .panw_prisma_airs import PanwPrismaAirsHandler

if TYPE_CHECKING:
    from hangarllm.types.guardrails import Guardrail, HangarllmParams


def initialize_guardrail(hangarllm_params: "HangarllmParams", guardrail: "Guardrail"):
    import hangarllm

    guardrail_name: Final = guardrail.get("guardrail_name")

    # Note: api_key and profile_name can be None - handler will use env vars or API key's linked profile
    if not guardrail_name:
        raise ValueError("PANW Prisma AIRS: guardrail_name is required")

    _panw_callback: Final = PanwPrismaAirsHandler(
        **{
            **hangarllm_params.model_dump(exclude_unset=True),
            "guardrail_name": guardrail_name,
            "event_hook": hangarllm_params.mode,
            "default_on": hangarllm_params.default_on or False,
        }
    )
    hangarllm.logging_callback_manager.add_hangarllm_callback(_panw_callback)

    return _panw_callback


guardrail_initializer_registry: Final = {
    SupportedGuardrailIntegrations.PANW_PRISMA_AIRS.value: initialize_guardrail,
}


guardrail_class_registry: Final = {
    SupportedGuardrailIntegrations.PANW_PRISMA_AIRS.value: PanwPrismaAirsHandler,
}
