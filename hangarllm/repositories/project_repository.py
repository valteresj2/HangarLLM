"""
Project repository for database operations on HangarLLM_ProjectTable.
"""

from collections.abc import Mapping
from typing import TYPE_CHECKING, Final

from hangarllm.models.project import HangarLLM_ProjectTable
from hangarllm.repositories.base_repository import BaseRepository
from hangarllm.repositories.prisma_protocols import TableActions
from hangarllm.repositories.table_repositories import PrismaTableRepository

if TYPE_CHECKING:
    from prisma import models as prisma_models


class _ProjectTable(PrismaTableRepository["prisma_models.HangarLLM_ProjectTable"]):
    table_name = "hangarllm_projecttable"


class ProjectRepository(BaseRepository[HangarLLM_ProjectTable]):
    """Repository for project database operations."""

    @property
    def table(self) -> TableActions["prisma_models.HangarLLM_ProjectTable"]:
        return _ProjectTable(self._prisma_client).table

    @property
    def model_class(self) -> type[HangarLLM_ProjectTable]:
        return HangarLLM_ProjectTable

    async def find_by_id(self, project_id: str, id_field: str = "project_id") -> HangarLLM_ProjectTable | None:
        return await super().find_by_id(project_id, id_field)

    async def find_by_alias(self, project_alias: str) -> HangarLLM_ProjectTable | None:
        """Find a project by alias."""
        projects: Final = await self.find_many(where={"project_alias": project_alias})
        return projects[0] if projects else None

    async def find_by_team_id(self, team_id: str) -> list[HangarLLM_ProjectTable]:
        """Find all projects belonging to a team."""
        return await self.find_many(where={"team_id": team_id})

    async def create_project(
        self,
        created_by: str,
        project_id: str | None = None,
        project_alias: str | None = None,
        description: str | None = None,
        team_id: str | None = None,
        budget_id: str | None = None,
        metadata: Mapping[str, object] | None = None,
        models: list[str] | None = None,
        model_rpm_limit: dict[str, int] | None = None,
        model_tpm_limit: dict[str, int] | None = None,
        object_permission_id: str | None = None,
    ) -> HangarLLM_ProjectTable:
        """Create a new project."""
        data: Final[dict[str, object]] = {
            "created_by": created_by,
            "updated_by": created_by,
        }
        if project_id is not None:
            data["project_id"] = project_id
        if project_alias is not None:
            data["project_alias"] = project_alias
        if description is not None:
            data["description"] = description
        if team_id is not None:
            data["team_id"] = team_id
        if budget_id is not None:
            data["budget_id"] = budget_id
        if metadata is not None:
            data["metadata"] = metadata
        if models is not None:
            data["models"] = models
        if model_rpm_limit is not None:
            data["model_rpm_limit"] = model_rpm_limit
        if model_tpm_limit is not None:
            data["model_tpm_limit"] = model_tpm_limit
        if object_permission_id is not None:
            data["object_permission_id"] = object_permission_id

        return await self.create(data)

    async def update_project(
        self,
        project_id: str,
        updated_by: str,
        project_alias: str | None = None,
        description: str | None = None,
        team_id: str | None = None,
        budget_id: str | None = None,
        metadata: Mapping[str, object] | None = None,
        models: list[str] | None = None,
        model_rpm_limit: dict[str, int] | None = None,
        model_tpm_limit: dict[str, int] | None = None,
        blocked: bool | None = None,
        object_permission_id: str | None = None,
    ) -> HangarLLM_ProjectTable | None:
        """Update a project."""
        data: Final[dict[str, object]] = {"updated_by": updated_by}
        if project_alias is not None:
            data["project_alias"] = project_alias
        if description is not None:
            data["description"] = description
        if team_id is not None:
            data["team_id"] = team_id
        if budget_id is not None:
            data["budget_id"] = budget_id
        if metadata is not None:
            data["metadata"] = metadata
        if models is not None:
            data["models"] = models
        if model_rpm_limit is not None:
            data["model_rpm_limit"] = model_rpm_limit
        if model_tpm_limit is not None:
            data["model_tpm_limit"] = model_tpm_limit
        if blocked is not None:
            data["blocked"] = blocked
        if object_permission_id is not None:
            data["object_permission_id"] = object_permission_id

        return await self.update(project_id, data, id_field="project_id")

    async def delete_project(self, project_id: str) -> HangarLLM_ProjectTable | None:
        """Delete a project."""
        return await self.delete(project_id, id_field="project_id")

    async def update_spend(self, project_id: str, spend: float) -> HangarLLM_ProjectTable | None:
        """Update project spend."""
        return await self.update(project_id, {"spend": spend}, id_field="project_id")
