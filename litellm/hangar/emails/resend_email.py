"""Resend delivery - ``RESEND_API_KEY`` and ``RESEND_SENDER_EMAIL``/``EMAIL_SENDER``."""

import os
from typing import Final

from litellm._logging import verbose_proxy_logger
from litellm.hangar.emails.base_email import BaseEmailLogger
from litellm.llms.custom_httpx.http_handler import get_async_httpx_client, httpxSpecialProvider

RESEND_API_ENDPOINT: Final = "https://api.resend.com/emails"


class ResendEmailLogger(BaseEmailLogger):
    def __init__(self, internal_usage_cache=None, **kwargs: object) -> None:
        super().__init__(internal_usage_cache=internal_usage_cache, **kwargs)
        self.resend_api_key: str | None = os.getenv("RESEND_API_KEY")
        self.async_httpx_client = get_async_httpx_client(llm_provider=httpxSpecialProvider.LoggingCallback)

    async def send_email(self, from_email: str, to_email: list[str], subject: str, html_body: str) -> None:
        if not self.resend_api_key:
            raise ValueError("RESEND_API_KEY is not set")
        response: Final = await self.async_httpx_client.post(
            url=RESEND_API_ENDPOINT,
            json={
                "from": os.getenv("RESEND_SENDER_EMAIL") or from_email,
                "to": to_email,
                "subject": subject,
                "html": html_body,
            },
            headers={"Authorization": f"Bearer {self.resend_api_key}"},
        )
        verbose_proxy_logger.debug("HangarLLM Resend: status=%s", response.status_code)
        response.raise_for_status()
