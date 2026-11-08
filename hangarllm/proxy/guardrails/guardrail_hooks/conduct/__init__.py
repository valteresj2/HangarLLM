from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from hangarllm.types.guardrails import SupportedGuardrailIntegrations

from .conduct import ConductGuardrail

if TYPE_CHECKING:
    from hangarllm.integrations.custom_guardrail import CustomGuardrail
    from hangarllm.types.guardrails import Guardrail, HangarllmParams

DEFAULT_TIMEOUT_SECONDS: Final = 8.0
_NO_EXTRAS: Final[Mapping[str, object]] = MappingProxyType({})


def initialize_guardrail(
    hangarllm_params: HangarllmParams,
    guardrail: Guardrail,
    guardrail_cls: type[CustomGuardrail] = ConductGuardrail,
) -> CustomGuardrail:
    import hangarllm

    extras: Final = hangarllm_params.model_extra or _NO_EXTRAS
    _callback: Final = guardrail_cls(
        api_url=hangarllm_params.api_base,
        agent_token=hangarllm_params.api_key,
        workspace_id=extras.get("workspace_id"),
        tool_name=extras.get("tool_name", "llm_call"),
        unreachable_fallback=hangarllm_params.unreachable_fallback,
        timeout=DEFAULT_TIMEOUT_SECONDS if hangarllm_params.timeout is None else hangarllm_params.timeout,
        guardrail_name=guardrail.get("guardrail_name", ""),
        event_hook=hangarllm_params.mode,
        default_on=hangarllm_params.default_on,
        supported_event_hooks=guardrail_cls.get_supported_event_hooks(),
    )
    hangarllm.logging_callback_manager.add_hangarllm_callback(_callback)
    return _callback


guardrail_initializer_registry: Final = {
    SupportedGuardrailIntegrations.CONDUCT.value: initialize_guardrail,
}

guardrail_class_registry: Final = {
    SupportedGuardrailIntegrations.CONDUCT.value: ConductGuardrail,
}
