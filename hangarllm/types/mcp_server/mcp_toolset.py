from datetime import datetime

from pydantic import Field
from typing_extensions import TypedDict

from hangarllm.types.llms.base import HangarLLMBaseModel


class MCPToolsetTool(TypedDict):
    server_id: str
    tool_name: str


class MCPToolset(HangarLLMBaseModel):
    toolset_id: str
    toolset_name: str
    description: str | None = None
    tools: list[MCPToolsetTool] = Field(default=[])
    created_at: datetime | None = None
    created_by: str | None = None
    updated_at: datetime | None = None
    updated_by: str | None = None


class NewMCPToolsetRequest(HangarLLMBaseModel):
    toolset_name: str
    description: str | None = None
    tools: list[MCPToolsetTool] = Field(default=[])


class UpdateMCPToolsetRequest(HangarLLMBaseModel):
    toolset_id: str
    toolset_name: str | None = None
    description: str | None = None
    tools: list[MCPToolsetTool] | None = None
