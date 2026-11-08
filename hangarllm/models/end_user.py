"""
End-user table model.

Canonical definition for ``hangarllm_endusertable``. Re-exported from
``hangarllm.proxy._types`` for backwards compatibility.
"""

from typing import Literal

from pydantic import ConfigDict, Field, field_validator

from hangarllm.models.budget import HangarLLM_BudgetTable
from hangarllm.models.object_permission import HangarLLM_ObjectPermissionTable
from hangarllm.types.llms.base import HangarLLMPydanticObjectBase


class HangarLLM_EndUserTable(HangarLLMPydanticObjectBase):
    user_id: str
    blocked: bool
    alias: str | None = None
    spend: float = 0.0
    allowed_model_region: Literal["eu", "us"] | None = None
    default_model: str | None = None
    models: list[str] = Field(default_factory=list)
    budget_id: str | None = None
    hangarllm_budget_table: HangarLLM_BudgetTable | None = None
    object_permission_id: str | None = None
    object_permission: HangarLLM_ObjectPermissionTable | None = None

    @field_validator("spend", mode="before")
    @classmethod
    def default_null_spend_to_zero(cls, spend: object) -> object:
        return 0.0 if spend is None else spend

    model_config = ConfigDict(protected_namespaces=())
