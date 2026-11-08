from collections.abc import Callable
from typing import ClassVar

from pydantic import ConfigDict, Field

from hangarllm.types.llms.base import HangarLLMBaseModel


class MCPTool(HangarLLMBaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(arbitrary_types_allowed=True)
    name: str
    description: str
    input_schema: dict[str, object]
    handler: Callable
    server_id: str | None = Field(default=None, frozen=True)


class ToolSchema(HangarLLMBaseModel):
    name: str
    description: str
    inputSchema: dict[str, object]


class ListToolsResponse(HangarLLMBaseModel):
    tools: list[ToolSchema]
    nextCursor: str | None = None
    _meta: dict[str, object] | None = None


class CallToolRequest(HangarLLMBaseModel):
    method: str = "tools/call"
    params: dict[str, object]


class ContentItem(HangarLLMBaseModel):
    type: str
    text: str | None = None
