from typing import TYPE_CHECKING, Final

from hangarllm.types.guardrails import SupportedGuardrailIntegrations

from .cato_networks import CatoNetworksGuardrail

if TYPE_CHECKING:
    from hangarllm.types.guardrails import Guardrail, HangarllmParams


def initialize_guardrail(hangarllm_params: "HangarllmParams", guardrail: "Guardrail"):
    import hangarllm
    from hangarllm.proxy.guardrails.guardrail_hooks.cato_networks import (
        CatoNetworksGuardrail,
    )

    _cato_callback: Final = CatoNetworksGuardrail(
        api_base=hangarllm_params.api_base,
        api_key=hangarllm_params.api_key,
        guardrail_name=guardrail.get("guardrail_name", ""),
        event_hook=hangarllm_params.mode,
        default_on=hangarllm_params.default_on,
        inspect_embeddings=hangarllm_params.inspect_embeddings,
        ssl_verify=getattr(hangarllm_params, "ssl_verify", None),
        timeout=hangarllm_params.timeout,
    )
    hangarllm.logging_callback_manager.add_hangarllm_callback(_cato_callback)

    return _cato_callback


guardrail_initializer_registry: Final = {
    SupportedGuardrailIntegrations.CATO_NETWORKS.value: initialize_guardrail,
}


guardrail_class_registry: Final = {
    SupportedGuardrailIntegrations.CATO_NETWORKS.value: CatoNetworksGuardrail,
}
