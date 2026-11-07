"""
Blocked end-user guardrail (``callbacks: ["blocked_user_check"]``).

Rejects requests whose end-user id (OpenAI ``user`` param, or
``metadata.end_user_id`` / ``litellm_metadata.end_user_id``) is either listed in
``litellm_settings.blocked_user_list`` (list or path to a file) or marked
``blocked`` in the end-user table (managed through ``/customer/block`` and
``/customer/unblock``).
"""

from collections.abc import Mapping
from typing import Final

from fastapi import HTTPException

import litellm
from litellm._logging import verbose_proxy_logger
from litellm.hangar.guardrails._text import load_list_setting
from litellm.integrations.custom_logger import CustomLogger

_CACHE_TTL_SECONDS: Final = 60


def _end_user_id(data: Mapping[str, object]) -> str | None:
    user: Final = data.get("user")
    if isinstance(user, str) and user:
        return user
    for slot in ("litellm_metadata", "metadata"):
        metadata = data.get(slot)
        if isinstance(metadata, Mapping):
            end_user = metadata.get("end_user_id") or metadata.get("user_api_key_end_user_id")
            if isinstance(end_user, str) and end_user:
                return end_user
    return None


class HangarBlockedUserList(CustomLogger):
    def __init__(self, prisma_client=None) -> None:
        super().__init__()
        self.prisma_client = prisma_client
        setting: Final = litellm.blocked_user_list
        self.blocked_user_list: list[str] = load_list_setting(setting) if setting is not None else []
        if isinstance(setting, str):
            # keep the module setting a mutable list so /customer/block|unblock can edit it
            litellm.blocked_user_list = self.blocked_user_list

    def _is_listed(self, user_id: str) -> bool:
        current: Final = litellm.blocked_user_list
        if isinstance(current, list):
            return user_id in current
        return user_id in self.blocked_user_list

    async def _is_blocked_in_db(self, user_id: str, cache) -> bool:
        if self.prisma_client is None:
            return False
        cache_key: Final = f"hangar:blocked_end_user:{user_id}"
        if cache is not None:
            try:
                cached = await cache.async_get_cache(key=cache_key)
                if cached is not None:
                    return bool(cached)
            except Exception:  # noqa: BLE001, S110 - cache is best effort
                pass
        try:
            row = await self.prisma_client.db.litellm_endusertable.find_unique(where={"user_id": user_id})
            blocked = bool(getattr(row, "blocked", False)) if row is not None else False
        except Exception as e:  # noqa: BLE001 - DB hiccups must not block traffic
            verbose_proxy_logger.debug("HangarLLM blocked_user_check: DB lookup failed - %s", e)
            return False
        if cache is not None:
            try:
                await cache.async_set_cache(key=cache_key, value=blocked, ttl=_CACHE_TTL_SECONDS)
            except Exception:  # noqa: BLE001, S110 - cache is best effort
                pass
        return blocked

    async def async_pre_call_hook(self, user_api_key_dict, cache, data: dict, call_type):
        user_id: Final = _end_user_id(data)
        if user_id is None:
            return data
        if self._is_listed(user_id) or await self._is_blocked_in_db(user_id, cache):
            raise HTTPException(
                status_code=400,
                detail={"error": f"User blocked from making LLM API calls. User={user_id}"},
            )
        return data


ENTERPRISE_BlockedUserList = HangarBlockedUserList
