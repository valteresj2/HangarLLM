"""
Persistence of per-event email toggles.

Stored in the ``HangarLLM_Config`` row ``general_settings`` under the
``email_settings`` key (``{"Virtual Key Created": true, ...}``) - the same
location the core model-deprecation mailer already reads its opt-in from.
"""

import time
from typing import Final

from hangarllm._logging import verbose_proxy_logger
from hangarllm.hangar.emails.types import DEFAULT_EMAIL_EVENT_SETTINGS, EmailEvent

_GENERAL_SETTINGS_PARAM: Final = "general_settings"
_EMAIL_SETTINGS_KEY: Final = "email_settings"
_CACHE_TTL_SECONDS: Final = 30.0

_cache: dict[str, object] = {"at": 0.0, "value": None}  # mutable-ok: tiny process-local TTL cache


def _prisma_client():
    from hangarllm.proxy.proxy_server import prisma_client

    return prisma_client


def _merge_with_defaults(stored: object) -> dict[str, bool]:
    merged: dict[str, bool] = dict(DEFAULT_EMAIL_EVENT_SETTINGS)  # mutable-ok: built and returned
    if isinstance(stored, dict):
        for event in EmailEvent:
            value = stored.get(event.value)
            if isinstance(value, bool):
                merged[event.value] = value
    return merged


async def load_email_settings(use_cache: bool = True) -> dict[str, bool]:
    now: Final = time.monotonic()
    cached: Final = _cache.get("value")
    if use_cache and isinstance(cached, dict) and now - float(_cache["at"]) < _CACHE_TTL_SECONDS:  # type: ignore[arg-type]
        return dict(cached)
    prisma_client: Final = _prisma_client()
    stored: object = None
    if prisma_client is not None:
        try:
            from hangarllm.repositories.config_repository import ConfigRepository

            row = await ConfigRepository(prisma_client).get_param(_GENERAL_SETTINGS_PARAM)
            if row is not None and isinstance(row.param_value, dict):
                stored = row.param_value.get(_EMAIL_SETTINGS_KEY)
        except Exception as e:  # noqa: BLE001 - settings fall back to defaults
            verbose_proxy_logger.debug("HangarLLM: could not load email settings - %s", e)
    settings: Final = _merge_with_defaults(stored)
    _cache["value"] = settings
    _cache["at"] = now
    return dict(settings)


async def save_email_settings(settings: dict[str, bool]) -> dict[str, bool]:
    prisma_client: Final = _prisma_client()
    if prisma_client is None:
        raise ValueError("HangarLLM needs a database (DATABASE_URL) to store email settings")
    from hangarllm.repositories.config_repository import ConfigRepository

    repo: Final = ConfigRepository(prisma_client, use_writer=True)
    row: Final = await repo.get_param(_GENERAL_SETTINGS_PARAM)
    general: Final = dict(row.param_value) if row is not None and isinstance(row.param_value, dict) else {}
    merged: Final = _merge_with_defaults(general.get(_EMAIL_SETTINGS_KEY))
    merged.update({k: v for k, v in settings.items() if k in merged})
    general[_EMAIL_SETTINGS_KEY] = merged
    await repo.set_param(_GENERAL_SETTINGS_PARAM, general)
    _cache["value"] = merged
    _cache["at"] = time.monotonic()
    return dict(merged)


async def is_email_event_enabled(event: EmailEvent) -> bool:
    return (await load_email_settings()).get(event.value, False)
