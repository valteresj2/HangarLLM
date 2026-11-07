"""
LLM Guard integration (``callbacks: ["llmguard_moderations"]``).

Calls a self-hosted `LLM Guard API <https://github.com/protectai/llm-guard>`_
(``LLM_GUARD_API_BASE``, e.g. ``http://llm-guard:8000``) ``/analyze/prompt`` and
blocks prompts it marks invalid.

``litellm_settings.llm_guard_mode``:

* ``all`` (default) - every request
* ``key-specific`` - only keys whose metadata has ``enable_llm_guard_check: true``
* ``request-specific`` - only requests with ``metadata.permissions.enable_llm_guard_check: true``
"""

import os
from collections.abc import Mapping
from typing import Final

from fastapi import HTTPException

import litellm
from litellm._logging import verbose_proxy_logger
from litellm.hangar.guardrails._text import last_user_text
from litellm.integrations.custom_logger import CustomLogger
from litellm.llms.custom_httpx.http_handler import get_async_httpx_client, httpxSpecialProvider


class HangarLLMGuard(CustomLogger):
    def __init__(self, mock_testing: bool = False, mock_redacted_text: dict | None = None) -> None:
        super().__init__()
        self.mock_testing: bool = mock_testing
        self.mock_redacted_text: dict | None = mock_redacted_text
        self.llm_guard_mode: str = litellm.llm_guard_mode
        base: Final = os.getenv("LLM_GUARD_API_BASE")
        if not base and not mock_testing:
            raise ValueError("llmguard_moderations needs LLM_GUARD_API_BASE (url of your LLM Guard API)")
        self.llm_guard_api_base: str = (base or "http://localhost:8000").rstrip("/") + "/"

    def should_proceed(self, user_api_key_dict: object, data: Mapping[str, object]) -> bool:
        mode: Final = self.llm_guard_mode
        if mode == "key-specific":
            metadata = getattr(user_api_key_dict, "metadata", None) or {}
            permissions = getattr(user_api_key_dict, "permissions", None) or {}
            return metadata.get("enable_llm_guard_check") is True or permissions.get("enable_llm_guard_check") is True
        if mode == "request-specific":
            metadata = data.get("metadata")
            permissions = metadata.get("permissions") if isinstance(metadata, Mapping) else None
            return isinstance(permissions, Mapping) and permissions.get("enable_llm_guard_check") is True
        return True

    async def moderation_check(self, text: str) -> dict:
        if self.mock_testing and self.mock_redacted_text is not None:
            result: dict = self.mock_redacted_text
        else:
            client: Final = get_async_httpx_client(llm_provider=httpxSpecialProvider.GuardrailCallback)
            headers: Final = (
                {"Authorization": f"Bearer {os.getenv('LLM_GUARD_API_KEY')}"} if os.getenv("LLM_GUARD_API_KEY") else {}
            )
            response: Final = await client.post(
                url=f"{self.llm_guard_api_base}analyze/prompt", json={"prompt": text}, headers=headers
            )
            response.raise_for_status()
            result = response.json()
        if result.get("is_valid") is False:
            raise HTTPException(
                status_code=400,
                detail={"error": "Violated content safety policy", "scanners": result.get("scanners")},
            )
        return result

    async def async_moderation_hook(self, data: dict, user_api_key_dict, call_type):
        if not self.should_proceed(user_api_key_dict, data):
            return
        text: Final = last_user_text(data)
        if not text:
            return
        try:
            await self.moderation_check(text)
        except HTTPException:
            raise
        except Exception as e:  # noqa: BLE001
            verbose_proxy_logger.error("HangarLLM llm_guard: API call failed - %s", e)
        return


_ENTERPRISE_LLMGuard = HangarLLMGuard
