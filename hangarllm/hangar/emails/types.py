"""Types for HangarLLM transactional emails."""

from enum import Enum

from pydantic import BaseModel

from hangarllm.types.integrations.model_deprecation_email import MODEL_DEPRECATION_EMAIL_EVENT
from hangarllm.types.integrations.slack_alerting import WebhookEvent


class EmailEvent(str, Enum):
    model_deprecations = MODEL_DEPRECATION_EMAIL_EVENT  # "Model Deprecations"
    virtual_key_created = "Virtual Key Created"
    new_user_invitation = "New User Invitation"
    virtual_key_rotated = "Virtual Key Rotated"
    soft_budget_crossed = "Soft Budget Crossed"
    max_budget_alert = "Max Budget Alert"


# What a fresh install sends: invitations on, everything else opt-in.
DEFAULT_EMAIL_EVENT_SETTINGS: dict[str, bool] = {
    EmailEvent.model_deprecations.value: False,
    EmailEvent.virtual_key_created.value: False,
    EmailEvent.new_user_invitation.value: True,
    EmailEvent.virtual_key_rotated.value: False,
    EmailEvent.soft_budget_crossed.value: True,
    EmailEvent.max_budget_alert.value: True,
}


class EmailEventSettings(BaseModel):
    event: EmailEvent
    enabled: bool


class EmailEventSettingsResponse(BaseModel):
    settings: list[EmailEventSettings]


class EmailEventSettingsUpdateRequest(BaseModel):
    settings: list[EmailEventSettings]


class SendKeyCreatedEmailEvent(WebhookEvent):
    virtual_key: str
    """The plaintext key - only ever placed in the email body, never logged."""


class SendKeyRotatedEmailEvent(WebhookEvent):
    virtual_key: str


class EmailParams(BaseModel):
    logo_url: str
    support_contact: str
    base_url: str
    recipient_email: str | None
    product_name: str = "HangarLLM"
