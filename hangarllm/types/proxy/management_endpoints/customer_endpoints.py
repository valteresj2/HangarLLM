from pydantic import Field

from hangarllm.models.budget import HangarLLM_BudgetTableFull
from hangarllm.models.end_user import HangarLLM_EndUserTable
from hangarllm.types.llms.base import HangarLLMBaseModel


class CustomerResponse(HangarLLM_EndUserTable):
    """Customer object returned by the /customer read+write endpoints.

    Nests the full budget response model so server-managed budget fields
    (budget_reset_at, created_at) survive response_model filtering, rather than
    the narrow write-allowlist shape HangarLLM_EndUserTable carries for internal use.
    """

    hangarllm_budget_table: HangarLLM_BudgetTableFull | None = None  # pyright: ignore


class BlockUsersResponse(HangarLLMBaseModel):
    blocked_users: list[HangarLLM_EndUserTable]


class UnblockUsersResponse(HangarLLMBaseModel):
    blocked_users: list[str] = Field(description="User IDs that remain blocked after this unblock call")


class DeleteCustomersResponse(HangarLLMBaseModel):
    deleted_customers: int
    message: str
