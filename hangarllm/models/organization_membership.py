"""
Organization membership table model.

Canonical definition for ``hangarllm_organizationmembership``. Re-exported from
``hangarllm.proxy._types`` for backwards compatibility.
"""

from datetime import datetime
from typing import Final

from pydantic import ConfigDict, model_validator

from hangarllm.models.budget import HangarLLM_BudgetTable
from hangarllm.types.llms.base import HangarLLMPydanticObjectBase


class HangarLLM_OrganizationMembershipTable(HangarLLMPydanticObjectBase):
    """Tracks which organizations a user belongs to and their spend within it."""

    user_id: str
    organization_id: str
    user_role: str | None = None
    spend: float = 0.0
    budget_id: str | None = None
    created_at: datetime
    updated_at: datetime
    user: object | None = None
    hangarllm_budget_table: HangarLLM_BudgetTable | None = None
    user_email: str | None = None

    model_config = ConfigDict(protected_namespaces=())

    @model_validator(mode="after")
    def populate_user_email(self) -> "HangarLLM_OrganizationMembershipTable":
        user: Final[object] = self.user
        if self.user_email is None and user is not None:
            if isinstance(user, dict):
                self.user_email = user.get("user_email")
            else:
                self.user_email = getattr(user, "user_email", None)
        return self
