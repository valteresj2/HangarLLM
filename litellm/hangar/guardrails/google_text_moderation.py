"""
Google Cloud Natural Language text moderation (``callbacks: ["google_text_moderation"]``).

Calls ``documents:moderateText`` and blocks the request when any category's
confidence reaches its threshold. Thresholds:

* ``litellm_settings.google_moderation_confidence_threshold`` - global (default 0.8)
* ``litellm_settings.<category>_confidence_threshold`` - per category, e.g.
  ``toxic_confidence_threshold: 0.6`` (category names lower-cased, spaces -> ``_``)

Auth: ``GOOGLE_TEXT_MODERATION_API_KEY`` / ``GOOGLE_API_KEY`` (API key) or
Application Default Credentials when ``google-auth`` is installed.
"""

import os
from typing import Final

from fastapi import HTTPException

import litellm
from litellm._logging import verbose_proxy_logger
from litellm.hangar.guardrails._text import request_texts
from litellm.integrations.custom_logger import CustomLogger
from litellm.llms.custom_httpx.http_handler import get_async_httpx_client, httpxSpecialProvider

MODERATE_TEXT_URL: Final = "https://language.googleapis.com/v2/documents:moderateText"
DEFAULT_CONFIDENCE_THRESHOLD: Final = 0.8


def _category_threshold(name: str) -> float:
    attr: Final = f"{name.lower().replace(' ', '_').replace('&', 'and')}_confidence_threshold"
    specific: Final = getattr(litellm, attr, None)
    if isinstance(specific, (int, float)):
        return float(specific)
    general: Final = litellm.google_moderation_confidence_threshold
    return float(general) if isinstance(general, (int, float)) else DEFAULT_CONFIDENCE_THRESHOLD


class HangarGoogleTextModeration(CustomLogger):
    def __init__(self) -> None:
        super().__init__()
        self.api_key: str | None = os.getenv("GOOGLE_TEXT_MODERATION_API_KEY") or os.getenv("GOOGLE_API_KEY")

    async def _auth(self) -> tuple[dict[str, str], dict[str, str]]:
        if self.api_key:
            return {}, {"key": self.api_key}
        try:
            import google.auth  # type: ignore[import-not-found]
            import google.auth.transport.requests  # type: ignore[import-not-found]

            credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-language"])
            credentials.refresh(google.auth.transport.requests.Request())
            return {"Authorization": f"Bearer {credentials.token}"}, {}
        except Exception as e:  # noqa: BLE001
            raise ValueError(
                "google_text_moderation needs GOOGLE_TEXT_MODERATION_API_KEY or Application Default Credentials"
            ) from e

    async def async_moderation_hook(self, data: dict, user_api_key_dict, call_type):
        text: Final = "\n".join(request_texts(data)).strip()
        if not text:
            return
        headers, params = await self._auth()
        client: Final = get_async_httpx_client(llm_provider=httpxSpecialProvider.GuardrailCallback)
        try:
            response = await client.post(
                url=MODERATE_TEXT_URL,
                json={"document": {"type": "PLAIN_TEXT", "content": text}},
                headers=headers,
                params=params,
            )
            response.raise_for_status()
            body = response.json()
        except Exception as e:  # noqa: BLE001
            verbose_proxy_logger.error("HangarLLM google_text_moderation: API call failed - %s", e)
            return
        violations: Final = [
            {"category": c.get("name"), "confidence": c.get("confidence")}
            for c in body.get("moderationCategories", [])
            if isinstance(c.get("confidence"), (int, float))
            and c["confidence"] >= _category_threshold(str(c.get("name")))
        ]
        if violations:
            raise HTTPException(
                status_code=400, detail={"error": "Violated content safety policy", "violations": violations}
            )
        return


ENTERPRISE_GoogleTextModeration = HangarGoogleTextModeration
