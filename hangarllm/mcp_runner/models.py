import hashlib
import json
from collections.abc import Mapping
from typing import Final, Literal

from pydantic import ConfigDict, Field

from hangarllm.types.llms.base import HangarLLMBaseModel

Launcher = Literal["npx", "uvx"]
INSTANCE_KEY_PATTERN: Final = r"^[0-9a-f]{64}$"


class PackageRef(HangarLLMBaseModel):
    """An npm or PyPI package pinned to one version, as an MCP server is launched with npx or uvx."""

    model_config = ConfigDict(frozen=True)

    launcher: Launcher
    name: str = Field(pattern=r"^(@[a-z0-9][\w.-]*/)?[A-Za-z0-9][\w.-]*$")
    version: str = Field(pattern=r"^[A-Za-z0-9][\w.+-]*$")
    command: str | None = Field(default=None, pattern=r"^[A-Za-z0-9][\w.-]*$")


class LockRequest(HangarLLMBaseModel):
    model_config = ConfigDict(frozen=True)

    package: PackageRef


class LockResult(HangarLLMBaseModel):
    model_config = ConfigDict(frozen=True)

    package: PackageRef
    lock: str


class InstanceSpec(HangarLLMBaseModel):
    """Everything the runner needs to start one MCP server for one credential binding."""

    model_config = ConfigDict(frozen=True)

    server_id: str = Field(min_length=1, max_length=200)
    package: PackageRef
    lock: str = Field(min_length=1)
    args: tuple[str, ...] = ()
    env: Mapping[str, str] = Field(default_factory=dict)
    egress_allow_hosts: tuple[str, ...] = ()
    idle_timeout_seconds: float = Field(default=600, gt=0, le=86_400)


class InstanceInfo(HangarLLMBaseModel):
    model_config = ConfigDict(frozen=True)

    instance_key: str
    server_id: str
    sessions: int


def instance_key(server_id: str, env: Mapping[str, str]) -> str:
    """One key per server and credential binding, so two users' secrets never share a process."""
    material: Final = json.dumps({"server_id": server_id, "env": dict(env)}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(material.encode()).hexdigest()
