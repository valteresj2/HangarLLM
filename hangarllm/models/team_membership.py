"""
Team membership table model.

Canonical definition for ``hangarllm_teammembership``. Re-exported from
``hangarllm.proxy._types`` for backwards compatibility.
"""

from hangarllm.models.budget import HangarLLM_BudgetTable, HangarLLM_BudgetTableFull
from hangarllm.types.llms.base import HangarLLMPydanticObjectBase


class HangarLLM_TeamMembership(HangarLLMPydanticObjectBase):
    user_id: str
    team_id: str
    budget_id: str | None = None
    spend: float | None = 0.0
    total_spend: float | None = 0.0
    hangarllm_budget_table: HangarLLM_BudgetTableFull | HangarLLM_BudgetTable | None = None

    def safe_get_team_member_rpm_limit(self) -> int | None:
        if self.hangarllm_budget_table is not None:
            return self.hangarllm_budget_table.rpm_limit
        return None

    def safe_get_team_member_tpm_limit(self) -> int | None:
        if self.hangarllm_budget_table is not None:
            return self.hangarllm_budget_table.tpm_limit
        return None
