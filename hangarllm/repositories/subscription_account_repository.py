"""
Subscription account repository for database operations on HangarLLM_SubscriptionAccountTable.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Final, Protocol, TypeAlias

from hangarllm.models.subscription_account import HangarLLM_SubscriptionAccountTable
from hangarllm.repositories.base_repository import BaseRepository, is_unique_violation
from hangarllm.repositories.prisma_protocols import TableActions
from hangarllm.repositories.table_repositories import PrismaTableRepository

if TYPE_CHECKING:
    from prisma import models as prisma_models


@dataclass(frozen=True, slots=True)
class DuplicateSubscriptionAccount:
    custom_llm_provider: str
    account_id: str


@dataclass(frozen=True, slots=True)
class SubscriptionAccountFeeFields:
    monthly_fee: float
    currency: str
    billing_period_start: str
    label: str | None


@dataclass(frozen=True, slots=True)
class KeepLabel:
    pass


@dataclass(frozen=True, slots=True)
class SetLabel:
    value: str | None


LabelChange: TypeAlias = KeepLabel | SetLabel


@dataclass(frozen=True, slots=True)
class SubscriptionAccountFeeChanges:
    monthly_fee: float | None = None
    currency: str | None = None
    billing_period_start: str | None = None
    label: LabelChange = KeepLabel()

    def columns(self) -> Mapping[str, float | str | None]:
        named: Final = {
            "monthly_fee": self.monthly_fee,
            "currency": self.currency,
            "billing_period_start": self.billing_period_start,
        }
        present: Final = {column: value for column, value in named.items() if value is not None}
        label_column: Final = {"label": self.label.value} if isinstance(self.label, SetLabel) else {}
        return MappingProxyType({**present, **label_column})


class SubscriptionAccountStore(Protocol):
    async def list_all(self) -> tuple[HangarLLM_SubscriptionAccountTable, ...]: ...

    async def find_by_id(self, id_value: str) -> HangarLLM_SubscriptionAccountTable | None: ...

    async def create_account(
        self, custom_llm_provider: str, account_id: str, fee: SubscriptionAccountFeeFields, created_by: str
    ) -> HangarLLM_SubscriptionAccountTable | DuplicateSubscriptionAccount: ...

    async def update_fee(
        self, subscription_account_id: str, changes: SubscriptionAccountFeeChanges, updated_by: str
    ) -> HangarLLM_SubscriptionAccountTable | None: ...

    async def delete_account(self, subscription_account_id: str) -> HangarLLM_SubscriptionAccountTable | None: ...


class _SubscriptionAccountTable(PrismaTableRepository["prisma_models.HangarLLM_SubscriptionAccountTable"]):
    table_name = "hangarllm_subscriptionaccounttable"


class SubscriptionAccountRepository(BaseRepository[HangarLLM_SubscriptionAccountTable]):
    def __init__(self, prisma_client: object) -> None:
        super().__init__(prisma_client)
        self._table: Final = _SubscriptionAccountTable(prisma_client)

    @property
    def table(self) -> TableActions["prisma_models.HangarLLM_SubscriptionAccountTable"]:
        return self._table.table

    @property
    def model_class(self) -> type[HangarLLM_SubscriptionAccountTable]:
        return HangarLLM_SubscriptionAccountTable

    async def list_all(self) -> tuple[HangarLLM_SubscriptionAccountTable, ...]:
        return tuple(await self.find_many(order={"created_at": "asc"}))

    async def find_by_id(
        self, id_value: str, id_field: str = "subscription_account_id"
    ) -> HangarLLM_SubscriptionAccountTable | None:
        return await super().find_by_id(id_value, id_field)

    async def create_account(
        self, custom_llm_provider: str, account_id: str, fee: SubscriptionAccountFeeFields, created_by: str
    ) -> HangarLLM_SubscriptionAccountTable | DuplicateSubscriptionAccount:
        try:
            return await self.create(
                {
                    "custom_llm_provider": custom_llm_provider,
                    "account_id": account_id,
                    "monthly_fee": fee.monthly_fee,
                    "currency": fee.currency,
                    "billing_period_start": fee.billing_period_start,
                    "label": fee.label,
                    "created_by": created_by,
                    "updated_by": created_by,
                }
            )
        except Exception as exc:
            if is_unique_violation(exc):
                return DuplicateSubscriptionAccount(custom_llm_provider=custom_llm_provider, account_id=account_id)
            raise

    async def update_fee(
        self, subscription_account_id: str, changes: SubscriptionAccountFeeChanges, updated_by: str
    ) -> HangarLLM_SubscriptionAccountTable | None:
        return await self.update(
            subscription_account_id, {**changes.columns(), "updated_by": updated_by}, id_field="subscription_account_id"
        )

    async def delete_account(self, subscription_account_id: str) -> HangarLLM_SubscriptionAccountTable | None:
        return await self.delete(subscription_account_id, id_field="subscription_account_id")
