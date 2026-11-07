"""SendGrid (v3 Mail Send API) delivery - ``SENDGRID_API_KEY`` and ``SENDGRID_SENDER_EMAIL``/``EMAIL_SENDER``."""

import os
from typing import Final

from litellm._logging import verbose_proxy_logger
from litellm.hangar.emails.base_email import BaseEmailLogger
from litellm.llms.custom_httpx.http_handler import get_async_httpx_client, httpxSpecialProvider

SENDGRID_API_URL: Final = "https://api.sendgrid.com/v3/mail/send"


class SendGridEmailLogger(BaseEmailLogger):
    def __init__(self, internal_usage_cache=None, **kwargs: object) -> None:
        super().__init__(internal_usage_cache=internal_usage_cache, **kwargs)
        self.sendgrid_api_key: str | None = os.getenv("SENDGRID_API_KEY")
        self.async_httpx_client = get_async_httpx_client(llm_provider=httpxSpecialProvider.LoggingCallback)

    async def send_email(self, from_email: str, to_email: list[str], subject: str, html_body: str) -> None:
        if not self.sendgrid_api_key:
            raise ValueError("SENDGRID_API_KEY is not set")
        payload: Final = {
            "personalizations": [{"to": [{"email": address} for address in to_email]}],
            "from": {"email": os.getenv("SENDGRID_SENDER_EMAIL") or from_email, "name": "HangarLLM"},
            "subject": subject,
            "content": [{"type": "text/html", "value": html_body}],
        }
        response: Final = await self.async_httpx_client.post(
            url=SENDGRID_API_URL,
            json=payload,
            headers={"Authorization": f"Bearer {self.sendgrid_api_key}", "Content-Type": "application/json"},
        )
        verbose_proxy_logger.debug("HangarLLM SendGrid: status=%s", response.status_code)
        response.raise_for_status()
