"""
Tag table model.

Canonical definition for ``hangarllm_tagtable``. Re-exported from
``hangarllm.proxy._types`` for backwards compatibility.
"""

from datetime import datetime

from pydantic import model_validator

from hangarllm.models.budget import HangarLLM_BudgetTable
from hangarllm.types.llms.base import HangarLLMPydanticObjectBase


class HangarLLM_TagTable(HangarLLMPydanticObjectBase):
    tag_name: str
    description: str | None = None
    models: list[str] = []
    model_info: dict | None = None
    spend: float = 0.0
    budget_id: str | None = None
    hangarllm_budget_table: HangarLLM_BudgetTable | None = None
    created_at: datetime | None = None
    created_by: str | None = None
    updated_at: datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def set_model_info(cls, values):
        if values.get("spend") is None:
            values.update({"spend": 0.0})
        if values.get("models") is None:
            values.update({"models": []})
        return values
