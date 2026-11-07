"""
OpenAI moderation check (``callbacks: ["openai_moderations"]``).

Runs the last user turn (or the whole prompt) through the moderation endpoint in
parallel with the LLM call and rejects the request when it is flagged. The model
defaults to ``omni-moderation-latest``; override with
``litellm_settings.openai_moderations_model_name`` (it may also be a router
model group, e.g. an Azure deployment).
"""

from typing import Final

from fastapi import HTTPException

import litellm
from litellm._logging import verbose_proxy_logger
from litellm.hangar.guardrails._text import request_texts
from litellm.integrations.custom_logger import CustomLogger

DEFAULT_MODERATION_MODEL: Final = "omni-moderation-latest"


class HangarOpenAIModeration(CustomLogger):
    def __init__(self, model_name: str | None = None) -> None:
        super().__init__()
        self.model_name: str = model_name or litellm.openai_moderations_model_name or DEFAULT_MODERATION_MODEL

    @staticmethod
    def _flagged_categories(response: object) -> list[str]:
        results: Final = getattr(response, "results", None) or []
        flagged: list[str] = []  # mutable-ok: collected category names
        for result in results:
            if not getattr(result, "flagged", False):
                continue
            categories = getattr(result, "categories", None)
            items = categories.model_dump() if hasattr(categories, "model_dump") else (categories or {})
            flagged.extend(name for name, hit in dict(items).items() if hit)
            if not flagged:
                flagged.append("flagged")
        return flagged

    async def async_moderation_hook(self, data: dict, user_api_key_dict, call_type):
        text: Final = "\n".join(request_texts(data)).strip()
        if not text:
            return
        from litellm.proxy.proxy_server import llm_router

        try:
            router_models: list[str] = []  # mutable-ok: local
            if llm_router is not None:
                try:
                    router_models = list(llm_router.get_model_names())
                except Exception:  # noqa: BLE001 - router API surface differs across versions
                    router_models = []
            if llm_router is not None and self.model_name in router_models:
                response = await llm_router.amoderation(model=self.model_name, input=text)
            else:
                response = await litellm.amoderation(model=self.model_name, input=text)
        except Exception as e:  # noqa: BLE001 - moderation outage should not take traffic down
            verbose_proxy_logger.error("HangarLLM openai_moderations: moderation call failed - %s", e)
            return
        flagged: Final = self._flagged_categories(response)
        if flagged:
            raise HTTPException(
                status_code=400,
                detail={"error": "Violated content safety policy", "categories": sorted(set(flagged))},
            )
        return


ENTERPRISE_OpenAI_Moderation = HangarOpenAIModeration
