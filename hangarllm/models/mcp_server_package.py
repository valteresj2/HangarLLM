from typing import Protocol

from pydantic import ConfigDict

from hangarllm.mcp_runner.models import PackageRef
from hangarllm.types.llms.base import HangarLLMBaseModel


class MCPServerPackage(HangarLLMBaseModel):
    """What a local MCP server runs in the sandbox: one locked package and the hosts it may reach."""

    model_config = ConfigDict(frozen=True)

    server_id: str
    package: PackageRef
    lock: str
    egress_allow_hosts: tuple[str, ...] = ()


class MCPServerPackageStore(Protocol):
    async def get_package(self, server_id: str) -> MCPServerPackage | None: ...

    async def save_package(self, package: MCPServerPackage, updated_by: str) -> MCPServerPackage: ...
