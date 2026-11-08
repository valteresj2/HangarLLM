"""
Object permission table model.

Canonical definition for ``hangarllm_objectpermissiontable``. Re-exported from
``hangarllm.proxy._types`` for backwards compatibility.
"""

from hangarllm.types.llms.base import HangarLLMPydanticObjectBase


class HangarLLM_ObjectPermissionTable(HangarLLMPydanticObjectBase):
    """Represents a HangarLLM_ObjectPermissionTable record"""

    object_permission_id: str
    mcp_servers: list[str] | None = []
    mcp_access_groups: list[str] | None = []
    mcp_tool_permissions: dict[str, list[str]] | None = None
    vector_stores: list[str] | None = []
    agents: list[str] | None = []
    agent_access_groups: list[str] | None = []
    models: list[str] | None = []
    mcp_toolsets: list[str] | None = None
    blocked_tools: list[str] | None = []
    search_tools: list[str] | None = []
    mcp_tool_search_enabled: bool | None = None
    skills: list[str] | None = None
