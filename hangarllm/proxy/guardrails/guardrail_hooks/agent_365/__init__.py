from typing import TYPE_CHECKING, Final

from hangarllm._logging import verbose_proxy_logger
from hangarllm.types.guardrails import SupportedGuardrailIntegrations

from .agent_365 import Agent365Guardrail

if TYPE_CHECKING:
    from hangarllm.llms.custom_httpx.http_handler import AsyncHTTPHandler
    from hangarllm.types.guardrails import Guardrail, HangarllmParams


def initialize_guardrail(
    hangarllm_params: "HangarllmParams",
    guardrail: "Guardrail",
    *,
    async_handler: "AsyncHTTPHandler | None" = None,
) -> Agent365Guardrail:
    import hangarllm
    from hangarllm.secret_managers.main import get_secret_str

    tenant_id: Final = hangarllm_params.tenant_id or get_secret_str("AGENT365_TENANT_ID")
    client_id: Final = hangarllm_params.client_id or get_secret_str("AGENT365_CLIENT_ID")
    client_secret: Final = (
        hangarllm_params.client_secret or hangarllm_params.api_key or get_secret_str("AGENT365_CLIENT_SECRET")
    )

    if not tenant_id:
        raise ValueError("Microsoft Agent 365: tenant_id is required")
    if not client_id:
        raise ValueError("Microsoft Agent 365: client_id is required")
    if not client_secret:
        raise ValueError(
            "Microsoft Agent 365: client secret is required. Set client_secret, api_key, or AGENT365_CLIENT_SECRET"
        )

    guardrail_name: Final = guardrail.get("guardrail_name")
    if not guardrail_name:
        raise ValueError("Microsoft Agent 365: guardrail_name is required")

    extras: Final = hangarllm_params.model_extra or {}
    ignored_overrides: Final = tuple(
        key
        for key, value in (
            ("api_base", hangarllm_params.api_base),
            ("resource_app_id", extras.get("resource_app_id")),
            ("agent_id", extras.get("agent_id")),
        )
        if value is not None
    )
    if ignored_overrides:
        verbose_proxy_logger.warning(
            "Microsoft Agent 365 (%s): ignoring %s; evaluations always go to the production Agent 365 endpoint "
            "and the agent identity is the caller's key alias",
            guardrail_name,
            ", ".join(ignored_overrides),
        )

    agent_365_guardrail: Final = Agent365Guardrail(
        guardrail_name=guardrail_name,
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
        request_timeout=hangarllm_params.timeout if hangarllm_params.timeout is not None else 10.0,
        unreachable_fallback=hangarllm_params.unreachable_fallback,
        async_handler=async_handler,
        event_hook=hangarllm_params.mode,
        default_on=hangarllm_params.default_on,
    )
    hangarllm.logging_callback_manager.add_hangarllm_callback(agent_365_guardrail)
    return agent_365_guardrail


guardrail_initializer_registry: Final = {
    SupportedGuardrailIntegrations.AGENT_365.value: initialize_guardrail,
}

guardrail_class_registry: Final = {
    SupportedGuardrailIntegrations.AGENT_365.value: Agent365Guardrail,
}
