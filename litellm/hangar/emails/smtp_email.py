"""SMTP email delivery (``SMTP_HOST``, ``SMTP_PORT``, ``SMTP_USERNAME``, ``SMTP_PASSWORD``, ``SMTP_SENDER_EMAIL``)."""

from litellm._logging import verbose_proxy_logger
from litellm.hangar.emails.base_email import BaseEmailLogger


class SMTPEmailLogger(BaseEmailLogger):
    async def send_email(self, from_email: str, to_email: list[str], subject: str, html_body: str) -> None:
        from litellm.proxy.utils import send_email

        for recipient in to_email:
            try:
                await send_email(receiver_email=recipient, subject=subject, html=html_body)
            except Exception as e:  # noqa: BLE001 - one bad recipient must not block the rest
                verbose_proxy_logger.error("HangarLLM SMTP: failed to email %s - %s", recipient, e)
