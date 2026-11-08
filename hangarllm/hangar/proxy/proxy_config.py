"""
HangarLLM proxy-level settings loaded from ``general_settings``.

* ``custom_auth_settings.mode`` - how a user-defined ``custom_auth`` combines with
  the built-in key auth:

  - ``on`` (default): custom auth decides; its errors are returned to the caller.
  - ``auto``: try custom auth first; if it raises, fall back to virtual-key auth.
  - ``off``: ignore ``custom_auth`` and use virtual-key auth only.

* ``DOCS_DESCRIPTION`` / ``docs_description`` - text shown on the public model hub
  and Swagger page.
"""

import os
from collections.abc import Mapping
from typing import Final

from hangarllm._logging import verbose_proxy_logger

custom_auth_settings: dict | None = None


class HangarProxyConfig:
    async def load_enterprise_config(self, general_settings: Mapping[str, object]) -> None:
        global custom_auth_settings
        settings: Final = general_settings.get("custom_auth_settings")
        if settings is not None:
            if not isinstance(settings, Mapping):
                raise ValueError("general_settings.custom_auth_settings must be a mapping, e.g. {'mode': 'auto'}")
            mode: Final = settings.get("mode", "on")
            if mode not in ("on", "off", "auto"):
                raise ValueError(f"custom_auth_settings.mode must be one of on/off/auto, got {mode!r}")
            custom_auth_settings = dict(settings)  # rebind-ok: config load
            verbose_proxy_logger.info("HangarLLM: custom auth mode=%s", mode)
        docs_description: Final = general_settings.get("docs_description")
        if isinstance(docs_description, str):
            os.environ.setdefault("DOCS_DESCRIPTION", docs_description)

    # Hangar-style alias
    load_hangar_config = load_enterprise_config

    @staticmethod
    def get_custom_docs_description() -> str | None:
        return os.getenv("DOCS_DESCRIPTION") or None


EnterpriseProxyConfig = HangarProxyConfig
