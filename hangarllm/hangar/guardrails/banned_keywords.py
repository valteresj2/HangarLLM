"""
Banned-keywords guardrail (``callbacks: ["banned_keywords"]``).

``hangarllm_settings.banned_keywords_list`` is a list of words / phrases or a path
to a newline-separated file. Matching is case-insensitive and applied to the
prompt (pre-call) and to the model's answer (post-call).
"""

import re
from typing import Final

from fastapi import HTTPException

import hangarllm
from hangarllm._logging import verbose_proxy_logger
from hangarllm.hangar.guardrails._text import load_list_setting, request_texts, response_texts
from hangarllm.integrations.custom_logger import CustomLogger


class HangarBannedKeywords(CustomLogger):
    def __init__(self, banned_keywords: list[str] | str | None = None) -> None:
        super().__init__()
        source: Final = banned_keywords if banned_keywords is not None else hangarllm.banned_keywords_list
        keywords: Final = load_list_setting(source)
        if not keywords:
            raise ValueError("banned_keywords callback enabled but hangarllm_settings.banned_keywords_list is empty")
        self.banned_keywords_list: list[str] = [k.lower() for k in keywords]
        self._pattern: re.Pattern[str] = re.compile(
            "|".join(re.escape(k) for k in sorted(self.banned_keywords_list, key=len, reverse=True)), re.IGNORECASE
        )

    def find_banned(self, text: str) -> str | None:
        match: Final = self._pattern.search(text)
        return match.group(0).lower() if match else None

    def test_violation(self, test_str: str) -> None:
        keyword: Final = self.find_banned(test_str)
        if keyword is not None:
            verbose_proxy_logger.info("HangarLLM banned_keywords: blocked keyword %r", keyword)
            raise HTTPException(status_code=400, detail={"error": f"Keyword banned. Keyword={keyword}"})

    async def async_pre_call_hook(self, user_api_key_dict, cache, data: dict, call_type):
        for text in request_texts(data):
            self.test_violation(text)
        return data

    async def async_post_call_success_hook(self, data: dict, user_api_key_dict, response):
        for text in response_texts(response):
            self.test_violation(text)
        return response

    async def async_post_call_streaming_hook(self, user_api_key_dict, response: str):
        self.test_violation(response)
        return response


ENTERPRISE_BannedKeywords = HangarBannedKeywords
