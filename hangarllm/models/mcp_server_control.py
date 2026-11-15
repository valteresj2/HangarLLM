from typing import Protocol

from pydantic import ConfigDict

from hangarllm.types.llms.base import HangarLLMBaseModel


class MCPServerControl(HangarLLMBaseModel):
    model_config = ConfigDict(frozen=True)

    server_id: str
    disabled: bool = False
    disabled_tools: frozenset[str] = frozenset()


class MCPServerControlStore(Protocol):
    async def list_controls(self) -> tuple[MCPServerControl, ...]: ...

    async def set_server_disabled(self, server_id: str, disabled: bool, updated_by: str) -> MCPServerControl: ...

    async def set_tool_disabled(
        self, server_id: str, tool_name: str, disabled: bool, updated_by: str
    ) -> MCPServerControl: ...

    async def delete_control(self, server_id: str) -> None: ...
