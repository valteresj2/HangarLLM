"""How the gateway hands local (stdio) MCP servers to the sandboxed MCP runner."""

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import httpx
from fastapi import HTTPException, status

from hangarllm._logging import verbose_proxy_logger
from hangarllm.mcp_runner.models import InstanceSpec, LockRequest, LockResult, PackageRef, instance_key
from hangarllm.models.mcp_server_package import MCPServerPackage

_REGISTER_TIMEOUT_SECONDS: Final = 600.0
_CONTROL_TIMEOUT_SECONDS: Final = 10.0
_NPX_FLAGS_WITH_VALUE: Final = frozenset({"-p", "--package", "-c", "--call"})
_UVX_FLAGS_WITH_VALUE: Final = frozenset({"--with", "--python", "-p", "--index", "--index-url"})


@dataclass(frozen=True, slots=True)
class RunnerConfig:
    url: str
    token: str


def runner_config() -> RunnerConfig:
    token_file: Final = os.environ.get("HANGARLLM_MCP_RUNNER_TOKEN_FILE")
    token: Final = (
        Path(token_file).read_text().strip() if token_file else os.environ.get("HANGARLLM_MCP_RUNNER_TOKEN", "")
    )
    url: Final = os.environ.get("HANGARLLM_MCP_RUNNER_URL", "").rstrip("/")
    if not url or not token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Local MCP servers run in the MCP runner, but HANGARLLM_MCP_RUNNER_URL or its token is not set.",
        )
    return RunnerConfig(url=url, token=token)


def _split_spec(spec: str, separator: str) -> tuple[str, str] | None:
    scoped: Final = spec.startswith("@")
    name, found, version = spec[1:].partition(separator) if scoped else spec.partition(separator)
    if not found or not version:
        return None
    return ("@" + name if scoped else name), version


@dataclass(frozen=True, slots=True)
class LaunchCommand:
    package: PackageRef
    args: tuple[str, ...]


def _first_positional(args: Sequence[str], flags_with_value: frozenset[str]) -> int | None:
    flag_values: Final = frozenset(index + 1 for index, arg in enumerate(args) if arg in flags_with_value)
    return next((index for index, arg in enumerate(args) if index not in flag_values and not arg.startswith("-")), None)


def parse_launch_command(command: str | None, args: Sequence[str] | None) -> LaunchCommand:
    """Read the package and version out of ``npx pkg@1.2.3 ...`` or ``uvx pkg==1.2.3 ...``.

    Only pinned npx and uvx servers can run in the sandbox, because the runner installs exactly the locked
    version. Anything else is refused with the reason, so an admin can pin it or register it as remote.
    """
    launcher: Final = os.path.basename(command or "").lower().removesuffix(".cmd").removesuffix(".exe")
    argv: Final = tuple(args or ())
    if launcher not in ("npx", "uvx"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Only npx and uvx servers run in the MCP runner, not '{command}'. "
            "Pin an npx or uvx package, or run the server yourself and register it as a remote server.",
        )
    index: Final = _first_positional(argv, _NPX_FLAGS_WITH_VALUE if launcher == "npx" else _UVX_FLAGS_WITH_VALUE)
    split: Final = _split_spec(argv[index], "@" if launcher == "npx" else "==") if index is not None else None
    if index is None or split is None:
        example: Final = "npx some-server@1.2.3" if launcher == "npx" else "uvx some-server==1.2.3"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"The MCP runner only runs pinned packages. Write the version in the command, as in '{example}'.",
        )
    name, version = split
    return LaunchCommand(
        package=PackageRef(launcher="npx" if launcher == "npx" else "uvx", name=name, version=version),
        args=argv[index + 1 :],
    )


class RunnerClient:
    def __init__(self, config: RunnerConfig, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._config = config
        self._transport = transport

    def _client(self, timeout: float) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._config.url,
            headers={"Authorization": f"Bearer {self._config.token}"},
            timeout=timeout,
            transport=self._transport,
        )

    @property
    def auth_headers(self) -> Mapping[str, str]:
        return {"Authorization": f"Bearer {self._config.token}"}

    def instance_url(self, key: str) -> str:
        return f"{self._config.url}/v1/instances/{key}/mcp"

    async def lock(self, package: PackageRef) -> str:
        async with self._client(_REGISTER_TIMEOUT_SECONDS) as client:
            response: Final = await client.post(
                "/v1/packages/lock", json=LockRequest(package=package).model_dump(mode="json")
            )
        if response.status_code != status.HTTP_200_OK:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"The MCP runner could not lock the package: {response.text[:500]}",
            )
        return LockResult.model_validate_json(response.content).lock

    async def register(self, stored: MCPServerPackage, launch: LaunchCommand, env: Mapping[str, str]) -> str:
        key: Final = instance_key(stored.server_id, env)
        spec: Final = InstanceSpec(
            server_id=stored.server_id,
            package=stored.package,
            lock=stored.lock,
            args=launch.args,
            env=dict(env),
            egress_allow_hosts=stored.egress_allow_hosts,
        )
        try:
            async with self._client(_REGISTER_TIMEOUT_SECONDS) as client:
                response: Final = await client.put(f"/v1/instances/{key}", json=spec.model_dump(mode="json"))
        except httpx.HTTPError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"The MCP runner is unreachable for server {stored.server_id}: {type(error).__name__}",
            ) from error
        if response.status_code != status.HTTP_204_NO_CONTENT:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"The MCP runner refused server {stored.server_id}: {response.text[:500]}",
            )
        return self.instance_url(key)

    async def stop_server(self, server_id: str) -> None:
        try:
            async with self._client(_CONTROL_TIMEOUT_SECONDS) as client:
                await client.delete(f"/v1/servers/{server_id}/instances")
        except httpx.HTTPError as error:
            verbose_proxy_logger.warning("Could not stop MCP runner instances of server %s: %s", server_id, error)


def require_locked_package(server_id: str, stored: MCPServerPackage | None, launch: LaunchCommand) -> MCPServerPackage:
    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"MCP server {server_id} has no locked package yet. "
            f"An admin locks it with POST /v1/mcp/server/{server_id}/package.",
        )
    if (stored.package.launcher, stored.package.name, stored.package.version) != (
        launch.package.launcher,
        launch.package.name,
        launch.package.version,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"MCP server {server_id} now runs {launch.package.name}@{launch.package.version}, "
            f"but the locked package is {stored.package.name}@{stored.package.version}. Lock it again.",
        )
    return stored
