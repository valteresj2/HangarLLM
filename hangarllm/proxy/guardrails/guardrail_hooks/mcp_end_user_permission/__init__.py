from collections.abc import Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING, Final, Protocol, cast

from hangarllm.types.guardrails import SupportedGuardrailIntegrations

from .mcp_end_user_permission import MCPEndUserPermissionGuardrail

if TYPE_CHECKING:
    from hangarllm.types.guardrails import Guardrail, HangarllmParams


class _ParamsLookup(Protocol):
    def get(self, key: str, /) -> object: ...


_NO_PARAMS: Final = MappingProxyType[str, object]({})


def initialize_guardrail(hangarllm_params: "HangarllmParams", guardrail: "Guardrail"):
    import hangarllm

    # Default to always-on. Only disable if the user explicitly sets default_on: false.
    # We check the raw guardrail dict because HangarllmParams normalizes None → False,
    # making it impossible to distinguish "not set" from "explicitly false" via hangarllm_params.
    _raw_default_on: Final = (
        cast(Mapping[str, _ParamsLookup], guardrail).get("hangarllm_params", _NO_PARAMS).get("default_on")
    )
    _default_on: Final = _raw_default_on is not False

    _callback: Final = MCPEndUserPermissionGuardrail(
        guardrail_name=guardrail.get("guardrail_name", ""),
        event_hook=hangarllm_params.mode,
        default_on=_default_on,
    )
    hangarllm.logging_callback_manager.add_hangarllm_callback(_callback)
    return _callback


guardrail_initializer_registry: Final = {
    SupportedGuardrailIntegrations.MCP_END_USER_PERMISSION.value: initialize_guardrail,
}

guardrail_class_registry: Final = {
    SupportedGuardrailIntegrations.MCP_END_USER_PERMISSION.value: MCPEndUserPermissionGuardrail,
}
