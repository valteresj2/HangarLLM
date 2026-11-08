"""
Organization table model.

Canonical definition for ``hangarllm_organizationtable``. Re-exported from
``hangarllm.proxy._types`` for backwards compatibility.
"""

from hangarllm.models.budget import HangarLLM_BudgetTable
from hangarllm.models.object_permission import HangarLLM_ObjectPermissionTable
from hangarllm.models.user import HangarLLM_UserTable
from hangarllm.types.llms.base import HangarLLMPydanticObjectBase


class HangarLLM_OrganizationTable(HangarLLMPydanticObjectBase):
    """Represents user-controllable params for a HangarLLM_OrganizationTable record"""

    organization_id: str | None = None
    organization_alias: str | None = None
    budget_id: str
    spend: float = 0.0
    metadata: dict | None = None
    models: list[str] = []
    model_spend: dict | None = {}
    created_by: str
    updated_by: str
    users: list[HangarLLM_UserTable] | None = None
    hangarllm_budget_table: HangarLLM_BudgetTable | None = None
    object_permission: HangarLLM_ObjectPermissionTable | None = None
    object_permission_id: str | None = None
