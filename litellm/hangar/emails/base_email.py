"""
Base class for HangarLLM transactional email loggers.

Sub-classes only implement ``send_email`` (SMTP, SendGrid, Resend, ...). This
class decides *whether* to send (per-event toggles from ``/email/event_settings``),
*to whom* (user / team / alert recipients), renders the Hangar-branded templates
and de-duplicates budget alerts so a hot key does not flood an inbox.
"""

import os
from collections.abc import Iterable
from typing import Final, Literal

from litellm._logging import verbose_proxy_logger
from litellm.caching.dual_cache import DualCache
from litellm.hangar.emails import templates
from litellm.hangar.emails.settings import is_email_event_enabled
from litellm.hangar.emails.types import (
    EmailEvent,
    EmailParams,
    SendKeyCreatedEmailEvent,
    SendKeyRotatedEmailEvent,
)
from litellm.integrations.custom_logger import CustomLogger
from litellm.types.integrations.slack_alerting import CallInfo, WebhookEvent

BudgetAlertType = Literal[
    "token_budget",
    "user_budget",
    "soft_budget",
    "max_budget_alert",
    "team_budget",
    "organization_budget",
    "proxy_budget",
    "projected_limit_exceeded",
    "project_budget",
]

_BUDGET_ALERT_TITLES: Final[dict[str, str]] = {
    "soft_budget": "Soft budget crossed",
    "max_budget_alert": "Approaching max budget",
    "token_budget": "Key budget exceeded",
    "user_budget": "User budget exceeded",
    "team_budget": "Team budget exceeded",
    "organization_budget": "Organization budget exceeded",
    "project_budget": "Project budget exceeded",
    "proxy_budget": "Gateway budget exceeded",
    "projected_limit_exceeded": "Projected to exceed budget",
}
_BUDGET_ALERT_DEDUP_TTL_SECONDS: Final = 24 * 60 * 60


def _env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


class BaseEmailLogger(CustomLogger):
    """Renders and routes emails; ``send_email`` is a no-op logger in the base class."""

    def __init__(self, internal_usage_cache: DualCache | None = None, **kwargs: object) -> None:
        super().__init__()
        self.internal_usage_cache: DualCache = internal_usage_cache or DualCache()

    # ------------------------------------------------------------------ transport
    async def send_email(self, from_email: str, to_email: list[str], subject: str, html_body: str) -> None:
        verbose_proxy_logger.warning(
            "HangarLLM: no email provider configured (set SMTP_HOST, SENDGRID_API_KEY or RESEND_API_KEY); "
            "dropping email %r to %s",
            subject,
            to_email,
        )

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def sender_email() -> str:
        return (
            _env(
                "EMAIL_SENDER",
                "HANGARLLM_EMAIL_SENDER",
                "SMTP_SENDER_EMAIL",
                "SENDGRID_SENDER_EMAIL",
                "RESEND_SENDER_EMAIL",
            )
            or "notifications@hangarllm.local"
        )

    @staticmethod
    async def _lookup_user_email(user_id: str | None) -> str | None:
        if not user_id:
            return None
        try:
            from litellm.proxy.proxy_server import prisma_client
            from litellm.repositories.user_repository import UserRepository

            if prisma_client is None:
                return None
            row: Final = await UserRepository(prisma_client).table.find_unique(where={"user_id": user_id})
            email: Final = getattr(row, "user_email", None) if row is not None else None
            return email if isinstance(email, str) and email else None
        except Exception as e:  # noqa: BLE001 - recipient lookup is best effort
            verbose_proxy_logger.debug("HangarLLM: user email lookup failed for %s - %s", user_id, e)
            return None

    @staticmethod
    async def _lookup_team_name(team_id: str | None) -> str:
        if not team_id:
            return "your team"
        try:
            from litellm.proxy.proxy_server import prisma_client
            from litellm.repositories.team_repository import TeamRepository

            if prisma_client is None:
                return team_id
            row: Final = await TeamRepository(prisma_client).table.find_unique(where={"team_id": team_id})
            alias: Final = getattr(row, "team_alias", None) if row is not None else None
            return alias if isinstance(alias, str) and alias else team_id
        except Exception:  # noqa: BLE001
            return team_id

    @staticmethod
    async def _invitation_link(user_id: str | None, base_url: str) -> str:
        if not user_id:
            return f"{base_url.rstrip('/')}/ui"
        try:
            from pydantic import TypeAdapter

            from litellm.proxy.management_helpers.user_invitation import create_invitation_for_user
            from litellm.proxy.proxy_server import prisma_client
            from litellm.repositories.table_repositories import InvitationLinkRepository
            from litellm.types.integrations.slack_alerting import InvitationModel, InvitationNew
            from litellm.types.proxy.auth.user_api_key_auth import UserAPIKeyAuth

            if prisma_client is None:
                return f"{base_url.rstrip('/')}/ui"
            existing: Final = await InvitationLinkRepository(prisma_client).table.find_many(
                where={"user_id": user_id, "is_accepted": False}, order={"created_at": "desc"}
            )
            invitation: Final = (
                TypeAdapter(InvitationModel).validate_python(existing[0], from_attributes=True)
                if existing
                else TypeAdapter(InvitationModel).validate_python(
                    await create_invitation_for_user(
                        data=InvitationNew(user_id=user_id), user_api_key_dict=UserAPIKeyAuth(user_id=user_id)
                    ),
                    from_attributes=True,
                )
            )
            return f"{base_url.rstrip('/')}/ui/onboarding?invitation_id={invitation.id}"
        except Exception as e:  # noqa: BLE001
            verbose_proxy_logger.error("HangarLLM: could not create invitation link for %s - %s", user_id, e)
            return f"{base_url.rstrip('/')}/ui"

    @staticmethod
    def get_email_params(recipient_email: str | None) -> EmailParams:
        return EmailParams(
            logo_url=_env("EMAIL_LOGO_URL", "SMTP_SENDER_LOGO") or "",
            support_contact=_env("EMAIL_SUPPORT_CONTACT", "PROXY_ADMIN_EMAIL") or "admin@hangarllm.local",
            base_url=_env("PROXY_BASE_URL") or "http://localhost:4000",
            recipient_email=recipient_email,
        )

    async def _resolve_recipients(self, event: WebhookEvent | CallInfo, extra: Iterable[str] = ()) -> list[str]:
        primary: Final = event.user_email or await self._lookup_user_email(event.user_id)
        recipients: Final = [primary, *(event.alert_emails or ()), *extra]
        return list(dict.fromkeys(r for r in recipients if isinstance(r, str) and "@" in r))

    async def _deliver(self, recipients: list[str], subject: str, html: str) -> None:
        if not recipients:
            verbose_proxy_logger.debug("HangarLLM: email %r has no recipients, skipped", subject)
            return
        await self.send_email(from_email=self.sender_email(), to_email=recipients, subject=subject, html_body=html)

    # ------------------------------------------------------------------ events
    async def send_key_created_email(self, send_key_created_email_event: SendKeyCreatedEmailEvent) -> None:
        if not await is_email_event_enabled(EmailEvent.virtual_key_created):
            return
        recipients: Final = await self._resolve_recipients(send_key_created_email_event)
        params: Final = self.get_email_params(recipients[0] if recipients else None)
        subject, html = templates.key_created_email(
            recipient=params.recipient_email or "there",
            key=send_key_created_email_event.virtual_key,
            max_budget=send_key_created_email_event.max_budget,
            key_alias=send_key_created_email_event.key_alias,
            base_url=params.base_url,
            logo_url=params.logo_url or None,
            support=params.support_contact,
        )
        await self._deliver(recipients, subject, html)

    async def send_key_rotated_email(self, send_key_rotated_email_event: SendKeyRotatedEmailEvent) -> None:
        if not await is_email_event_enabled(EmailEvent.virtual_key_rotated):
            return
        recipients: Final = await self._resolve_recipients(send_key_rotated_email_event)
        params: Final = self.get_email_params(recipients[0] if recipients else None)
        subject, html = templates.key_rotated_email(
            recipient=params.recipient_email or "there",
            key=send_key_rotated_email_event.virtual_key,
            key_alias=send_key_rotated_email_event.key_alias,
            base_url=params.base_url,
            logo_url=params.logo_url or None,
            support=params.support_contact,
        )
        await self._deliver(recipients, subject, html)

    async def send_user_invitation_email(self, event: WebhookEvent) -> None:
        if not await is_email_event_enabled(EmailEvent.new_user_invitation):
            raise RuntimeError("'New User Invitation' emails are disabled in /email/event_settings")
        recipients: Final = await self._resolve_recipients(event)
        if not recipients:
            raise ValueError(f"No email address known for user_id={event.user_id}")
        params: Final = self.get_email_params(recipients[0])
        subject, html = templates.user_invitation_email(
            recipient=recipients[0],
            team_name=await self._lookup_team_name(event.team_id),
            invitation_link=await self._invitation_link(event.user_id, params.base_url),
            logo_url=params.logo_url or None,
            support=params.support_contact,
        )
        await self._deliver(recipients, subject, html)

    async def budget_alerts(self, type: BudgetAlertType, user_info: CallInfo) -> None:
        email_event: Final = EmailEvent.soft_budget_crossed if type == "soft_budget" else EmailEvent.max_budget_alert
        if not await is_email_event_enabled(email_event):
            return
        entity_id: Final = user_info.token or user_info.team_id or user_info.user_id or user_info.customer_id or "proxy"
        dedup_key: Final = f"hangar:email:budget:{type}:{entity_id}"
        try:
            if await self.internal_usage_cache.async_get_cache(key=dedup_key) is not None:
                return
            await self.internal_usage_cache.async_set_cache(
                key=dedup_key, value=True, ttl=_BUDGET_ALERT_DEDUP_TTL_SECONDS
            )
        except Exception as e:  # noqa: BLE001 - dedup is best effort
            verbose_proxy_logger.debug("HangarLLM: budget alert dedup cache unavailable - %s", e)
        extra: list[str] = []  # mutable-ok: threshold recipients
        for addresses in (user_info.max_budget_alert_emails or {}).values():
            extra.extend(addresses)
        recipients: Final = await self._resolve_recipients(user_info, extra)
        params: Final = self.get_email_params(recipients[0] if recipients else None)
        entity: Final = (
            f"Key '{user_info.key_alias}'"
            if user_info.key_alias
            else f"Team '{user_info.team_alias or user_info.team_id}'"
            if user_info.team_id
            else f"User '{user_info.user_email or user_info.user_id}'"
            if user_info.user_id
            else "Your gateway"
        )
        budget: Final = user_info.soft_budget if type == "soft_budget" else user_info.max_budget
        subject, html = templates.budget_alert_email(
            recipient=params.recipient_email or "there",
            alert_title=_BUDGET_ALERT_TITLES.get(type, "Budget alert"),
            entity=entity,
            spend=user_info.spend,
            budget=budget,
            base_url=params.base_url,
            logo_url=params.logo_url or None,
            support=params.support_contact,
        )
        await self._deliver(recipients, subject, html)


HangarBaseEmailLogger = BaseEmailLogger
