"""
Email event settings API (used by the console's *Email notifications* page).

``GET   /email/event_settings``        current toggles
``PATCH /email/event_settings``        update some toggles
``POST  /email/event_settings/reset``  back to defaults
"""

from typing import Final

from fastapi import APIRouter, Depends, HTTPException

from hangarllm.hangar.emails.settings import load_email_settings, save_email_settings
from hangarllm.hangar.emails.types import (
    DEFAULT_EMAIL_EVENT_SETTINGS,
    EmailEvent,
    EmailEventSettings,
    EmailEventSettingsResponse,
    EmailEventSettingsUpdateRequest,
)
from hangarllm.hangar.proxy._auth import require_proxy_admin
from hangarllm.proxy._types import UserAPIKeyAuth
from hangarllm.proxy.auth.user_api_key_auth import user_api_key_auth

router = APIRouter()
_AUTH: Final = Depends(user_api_key_auth)


def _as_response(settings: dict[str, bool]) -> EmailEventSettingsResponse:
    return EmailEventSettingsResponse(
        settings=[EmailEventSettings(event=event, enabled=settings.get(event.value, False)) for event in EmailEvent]
    )


@router.get("/email/event_settings", tags=["email management"], response_model=EmailEventSettingsResponse)
async def get_email_event_settings(
    user_api_key_dict: UserAPIKeyAuth = _AUTH,
) -> EmailEventSettingsResponse:
    """Get all email event settings."""
    require_proxy_admin(user_api_key_dict)
    return _as_response(await load_email_settings(use_cache=False))


@router.patch("/email/event_settings", tags=["email management"])
async def update_event_settings(
    request: EmailEventSettingsUpdateRequest,
    user_api_key_dict: UserAPIKeyAuth = _AUTH,
) -> dict:
    """Update the settings for email events."""
    require_proxy_admin(user_api_key_dict)
    try:
        saved: Final = await save_email_settings({s.event.value: s.enabled for s in request.settings})
    except ValueError as e:
        raise HTTPException(status_code=500, detail={"error": str(e)}) from e
    return {"message": "Email event settings updated successfully", **_as_response(saved).model_dump(mode="json")}


@router.post("/email/event_settings/reset", tags=["email management"])
async def reset_event_settings(
    user_api_key_dict: UserAPIKeyAuth = _AUTH,
) -> dict:
    """Reset all email event settings to defaults (new user invitations on, virtual key creation off)."""
    require_proxy_admin(user_api_key_dict)
    try:
        saved: Final = await save_email_settings(dict(DEFAULT_EMAIL_EVENT_SETTINGS))
    except ValueError as e:
        raise HTTPException(status_code=500, detail={"error": str(e)}) from e
    return {"message": "Email event settings reset to defaults", **_as_response(saved).model_dump(mode="json")}
