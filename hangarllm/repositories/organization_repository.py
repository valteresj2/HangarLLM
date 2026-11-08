"""
Organization repository for database operations on HangarLLM_OrganizationTable.
"""

from collections.abc import Mapping
from typing import TYPE_CHECKING, Final

from hangarllm.models.organization import HangarLLM_OrganizationTable
from hangarllm.repositories.base_repository import BaseRepository
from hangarllm.repositories.prisma_protocols import TableActions
from hangarllm.repositories.table_repositories import PrismaTableRepository

if TYPE_CHECKING:
    from prisma import models as prisma_models


class _OrganizationTable(PrismaTableRepository["prisma_models.HangarLLM_OrganizationTable"]):
    table_name = "hangarllm_organizationtable"


class OrganizationRepository(BaseRepository[HangarLLM_OrganizationTable]):
    """Repository for organization database operations."""

    @property
    def table(self) -> TableActions["prisma_models.HangarLLM_OrganizationTable"]:
        return _OrganizationTable(self._prisma_client).table

    @property
    def model_class(self) -> type[HangarLLM_OrganizationTable]:
        return HangarLLM_OrganizationTable

    async def find_by_id(
        self, organization_id: str, id_field: str = "organization_id"
    ) -> HangarLLM_OrganizationTable | None:
        return await super().find_by_id(organization_id, id_field)

    async def find_by_alias(self, organization_alias: str) -> HangarLLM_OrganizationTable | None:
        """Find an organization by alias."""
        organizations: Final = await self.find_many(where={"organization_alias": organization_alias})
        return organizations[0] if organizations else None

    async def create_organization(
        self,
        organization_alias: str,
        budget_id: str,
        created_by: str,
        organization_id: str | None = None,
        metadata: Mapping[str, object] | None = None,
        models: list[str] | None = None,
        object_permission_id: str | None = None,
    ) -> HangarLLM_OrganizationTable:
        """Create a new organization."""
        data: Final[dict[str, object]] = {
            "organization_alias": organization_alias,
            "budget_id": budget_id,
            "created_by": created_by,
            "updated_by": created_by,
        }
        if organization_id is not None:
            data["organization_id"] = organization_id
        if metadata is not None:
            data["metadata"] = metadata
        if models is not None:
            data["models"] = models
        if object_permission_id is not None:
            data["object_permission_id"] = object_permission_id

        return await self.create(data)

    async def update_organization(
        self,
        organization_id: str,
        updated_by: str,
        organization_alias: str | None = None,
        budget_id: str | None = None,
        metadata: Mapping[str, object] | None = None,
        models: list[str] | None = None,
        object_permission_id: str | None = None,
    ) -> HangarLLM_OrganizationTable | None:
        """Update an organization."""
        data: Final[dict[str, object]] = {"updated_by": updated_by}
        if organization_alias is not None:
            data["organization_alias"] = organization_alias
        if budget_id is not None:
            data["budget_id"] = budget_id
        if metadata is not None:
            data["metadata"] = metadata
        if models is not None:
            data["models"] = models
        if object_permission_id is not None:
            data["object_permission_id"] = object_permission_id

        return await self.update(organization_id, data, id_field="organization_id")

    async def delete_organization(self, organization_id: str) -> HangarLLM_OrganizationTable | None:
        """Delete an organization."""
        return await self.delete(organization_id, id_field="organization_id")

    async def update_spend(self, organization_id: str, spend: float) -> HangarLLM_OrganizationTable | None:
        """Update organization spend."""
        return await self.update(organization_id, {"spend": spend}, id_field="organization_id")
