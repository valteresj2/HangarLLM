from collections.abc import Mapping, Sequence
from datetime import datetime

from hangarllm.types.llms.base import HangarLLMBaseModel


class AccessGroupCreateRequest(HangarLLMBaseModel):
    access_group_name: str
    description: str | None = None
    access_model_names: list[str] | None = None
    access_mcp_server_ids: list[str] | None = None
    mcp_tool_permissions: Mapping[str, Sequence[str]] | None = None
    access_agent_ids: list[str] | None = None
    access_skill_names: tuple[str, ...] | None = None
    assigned_team_ids: list[str] | None = None
    assigned_key_ids: list[str] | None = None


class AccessGroupUpdateRequest(HangarLLMBaseModel):
    access_group_name: str | None = None
    description: str | None = None
    access_model_names: list[str] | None = None
    access_mcp_server_ids: list[str] | None = None
    mcp_tool_permissions: Mapping[str, Sequence[str]] | None = None
    access_agent_ids: list[str] | None = None
    access_skill_names: tuple[str, ...] | None = None
    assigned_team_ids: list[str] | None = None
    assigned_key_ids: list[str] | None = None


class AccessGroupResource(HangarLLMBaseModel):
    """A resource referenced by an access group. `name` is null when the id no longer resolves or has no alias."""

    id: str
    name: str | None


class AccessGroupResponse(HangarLLMBaseModel):
    access_group_id: str
    access_group_name: str
    description: str | None = None
    access_model_names: list[str]
    access_mcp_server_ids: list[str]
    mcp_tool_permissions: Mapping[str, Sequence[str]] | None = None
    access_agent_ids: list[str]
    access_skill_names: tuple[str, ...] = ()
    assigned_team_ids: list[str]
    assigned_key_ids: list[str]
    access_mcp_servers: tuple[AccessGroupResource, ...]
    access_agents: tuple[AccessGroupResource, ...]
    assigned_teams: tuple[AccessGroupResource, ...]
    assigned_keys: tuple[AccessGroupResource, ...]
    created_at: datetime
    created_by: str | None = None
    updated_at: datetime
    updated_by: str | None = None
