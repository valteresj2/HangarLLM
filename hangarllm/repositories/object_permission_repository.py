"""
ObjectPermission repository for database operations on HangarLLM_ObjectPermissionTable.
"""

from typing import TYPE_CHECKING, Final

from hangarllm.models.object_permission import HangarLLM_ObjectPermissionTable
from hangarllm.repositories.base_repository import BaseRepository
from hangarllm.repositories.prisma_protocols import TableActions
from hangarllm.repositories.table_repositories import PrismaTableRepository

if TYPE_CHECKING:
    from prisma import models as prisma_models


class _ObjectPermissionTable(PrismaTableRepository["prisma_models.HangarLLM_ObjectPermissionTable"]):
    table_name = "hangarllm_objectpermissiontable"


class ObjectPermissionRepository(BaseRepository[HangarLLM_ObjectPermissionTable]):
    """Repository for object permission database operations."""

    def __init__(self, prisma_client: object, *, use_writer: bool = False) -> None:
        super().__init__(prisma_client)
        self._use_writer = use_writer

    @property
    def table(self) -> TableActions["prisma_models.HangarLLM_ObjectPermissionTable"]:
        return _ObjectPermissionTable(self._prisma_client, use_writer=self._use_writer).table

    @property
    def model_class(self) -> type[HangarLLM_ObjectPermissionTable]:
        return HangarLLM_ObjectPermissionTable

    async def find_by_id(
        self, object_permission_id: str, id_field: str = "object_permission_id"
    ) -> HangarLLM_ObjectPermissionTable | None:
        return await super().find_by_id(object_permission_id, id_field)

    async def create_permission(
        self,
        mcp_servers: list[str] | None = None,
        mcp_access_groups: list[str] | None = None,
        mcp_tool_permissions: dict[str, list[str]] | None = None,
        vector_stores: list[str] | None = None,
        agents: list[str] | None = None,
        agent_access_groups: list[str] | None = None,
        models: list[str] | None = None,
        blocked_tools: list[str] | None = None,
        mcp_toolsets: list[str] | None = None,
        search_tools: list[str] | None = None,
        skills: list[str] | None = None,
    ) -> HangarLLM_ObjectPermissionTable:
        """Create a new object permission record."""
        data: Final[dict[str, object]] = {}
        if mcp_servers is not None:
            data["mcp_servers"] = mcp_servers
        if mcp_access_groups is not None:
            data["mcp_access_groups"] = mcp_access_groups
        if mcp_tool_permissions is not None:
            data["mcp_tool_permissions"] = mcp_tool_permissions
        if vector_stores is not None:
            data["vector_stores"] = vector_stores
        if agents is not None:
            data["agents"] = agents
        if agent_access_groups is not None:
            data["agent_access_groups"] = agent_access_groups
        if models is not None:
            data["models"] = models
        if blocked_tools is not None:
            data["blocked_tools"] = blocked_tools
        if mcp_toolsets is not None:
            data["mcp_toolsets"] = mcp_toolsets
        if search_tools is not None:
            data["search_tools"] = search_tools
        if skills is not None:
            data["skills"] = skills

        return await self.create(data)

    async def update_permission(
        self,
        object_permission_id: str,
        mcp_servers: list[str] | None = None,
        mcp_access_groups: list[str] | None = None,
        mcp_tool_permissions: dict[str, list[str]] | None = None,
        vector_stores: list[str] | None = None,
        agents: list[str] | None = None,
        agent_access_groups: list[str] | None = None,
        models: list[str] | None = None,
        blocked_tools: list[str] | None = None,
        mcp_toolsets: list[str] | None = None,
        search_tools: list[str] | None = None,
        skills: list[str] | None = None,
    ) -> HangarLLM_ObjectPermissionTable | None:
        """Update an object permission record."""
        data: Final[dict[str, object]] = {}
        if mcp_servers is not None:
            data["mcp_servers"] = mcp_servers
        if mcp_access_groups is not None:
            data["mcp_access_groups"] = mcp_access_groups
        if mcp_tool_permissions is not None:
            data["mcp_tool_permissions"] = mcp_tool_permissions
        if vector_stores is not None:
            data["vector_stores"] = vector_stores
        if agents is not None:
            data["agents"] = agents
        if agent_access_groups is not None:
            data["agent_access_groups"] = agent_access_groups
        if models is not None:
            data["models"] = models
        if blocked_tools is not None:
            data["blocked_tools"] = blocked_tools
        if mcp_toolsets is not None:
            data["mcp_toolsets"] = mcp_toolsets
        if search_tools is not None:
            data["search_tools"] = search_tools
        if skills is not None:
            data["skills"] = skills

        return await self.update(object_permission_id, data, id_field="object_permission_id")

    async def delete_permission(self, object_permission_id: str) -> HangarLLM_ObjectPermissionTable | None:
        """Delete an object permission record."""
        return await self.delete(object_permission_id, id_field="object_permission_id")
