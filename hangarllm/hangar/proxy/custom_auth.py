"""
Custom-auth orchestration (see ``custom_auth_settings`` in ``proxy_config``).

Return value contract (consumed by ``user_api_key_auth``):

* ``UserAPIKeyAuth`` - the request is authenticated by custom auth
* ``str``            - custom auth mapped the credential to a HangarLLM virtual key
* ``None``           - fall through to the built-in virtual-key auth
"""

from collections.abc import Awaitable, Callable
from typing import Final

from fastapi import Request

from hangarllm._logging import verbose_proxy_logger
from hangarllm.hangar.proxy import proxy_config


async def enterprise_custom_auth(
    request: Request,
    api_key: str,
    user_custom_auth: Callable[..., Awaitable[object]] | None,
) -> object | None:
    if user_custom_auth is None:
        return None
    settings: Final = proxy_config.custom_auth_settings or {}
    mode: Final = settings.get("mode", "on")
    if mode == "off":
        return None
    if mode == "auto":
        try:
            return await user_custom_auth(request, api_key)
        except Exception as e:  # noqa: BLE001 - "auto" means: fall back to key auth
            verbose_proxy_logger.debug("HangarLLM custom auth (auto) failed, falling back to key auth - %s", e)
            return None
    return await user_custom_auth(request, api_key)


hangar_custom_auth = enterprise_custom_auth
