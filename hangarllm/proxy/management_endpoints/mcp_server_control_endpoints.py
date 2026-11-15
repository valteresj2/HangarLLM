from typing import Annotated, Final

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import ConfigDict, StringConstraints

from hangarllm.constants import HANGARLLM_PROXY_ADMIN_NAME
from hangarllm.models.mcp_server_control import MCPServerControl, MCPServerControlStore
from hangarllm.models.mcp_server_package import MCPServerPackage, MCPServerPackageStore
from hangarllm.proxy._types import HangarllmTableNames, HangarllmUserRoles, UserAPIKeyAuth
from hangarllm.proxy.auth.user_api_key_auth import user_api_key_auth
from hangarllm.proxy.deps.repositories import MCPServerControlRepositoryDep, MCPServerPackageRepositoryDep
from hangarllm.proxy.management_helpers.audit_logs import create_object_audit_log, get_audit_log_changed_by
from hangarllm.proxy.mcp_server.runner_client import RunnerClient, parse_launch_command, runner_config
from hangarllm.proxy.mcp_server.server_controls import mcp_server_controls
from hangarllm.proxy.mcp_server.stdio_gate import runs_local_servers_in_runner
from hangarllm.types.llms.base import HangarLLMBaseModel
from hangarllm.types.mcp import MCPTransport
from hangarllm.types.mcp_server.mcp_server_manager import MCPServer

router: Final = APIRouter(prefix="/v1/mcp", tags=["mcp"])
_EGRESS_HOST_PATTERN: Final = r"^(\*\.)?[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+(:[0-9]{1,5})?$"


class MCPControlUpdate(HangarLLMBaseModel):
    model_config = ConfigDict(frozen=True)

    disabled: bool


async def _proxy_admin(
    user_api_key_dict: Annotated[UserAPIKeyAuth, Depends(user_api_key_auth)],
) -> UserAPIKeyAuth:
    if user_api_key_dict.user_role != HangarllmUserRoles.PROXY_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only proxy admins can disable MCP servers.")
    return user_api_key_dict


def _require_store(store: MCPServerControlStore | None) -> MCPServerControlStore:
    if store is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database not connected.")
    return store


def _require_known_server(server_id: str) -> MCPServer:
    from hangarllm.proxy.mcp_server.mcp_server_manager import global_mcp_server_manager

    server: Final = global_mcp_server_manager.get_mcp_server_by_id(server_id)
    if server is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"MCP server {server_id} not found.")
    return server


async def _apply_and_audit(
    control: MCPServerControl,
    disabled: bool,
    user_api_key_dict: UserAPIKeyAuth,
    hangarllm_changed_by: str | None,
) -> MCPServerControl:
    mcp_server_controls.apply(control)
    await create_object_audit_log(
        object_id=control.server_id,
        action="blocked" if disabled else "unblocked",
        hangarllm_changed_by=hangarllm_changed_by,
        user_api_key_dict=user_api_key_dict,
        hangarllm_proxy_admin_name=HANGARLLM_PROXY_ADMIN_NAME,
        table_name=HangarllmTableNames.MCP_SERVER_CONTROL_TABLE_NAME,
        after_value=control.model_dump_json(),
    )
    return control


def _changed_by(user_api_key_dict: UserAPIKeyAuth, hangarllm_changed_by: str | None) -> str:
    return (
        get_audit_log_changed_by(
            hangarllm_changed_by=hangarllm_changed_by,
            user_api_key_dict=user_api_key_dict,
            hangarllm_proxy_admin_name=HANGARLLM_PROXY_ADMIN_NAME,
        )
        or HANGARLLM_PROXY_ADMIN_NAME
    )


@router.post(
    "/server/{server_id}/control",
    description="Disable or re-enable every tool of an MCP server on all workers. Proxy admin only.",
    response_model=MCPServerControl,
)
async def set_mcp_server_disabled(
    server_id: str,
    update: MCPControlUpdate,
    user_api_key_dict: Annotated[UserAPIKeyAuth, Depends(_proxy_admin)],
    store: MCPServerControlRepositoryDep,
    hangarllm_changed_by: Annotated[str | None, Header()] = None,
) -> MCPServerControl:
    controls: Final = _require_store(store)
    _require_known_server(server_id)
    control: Final = await controls.set_server_disabled(
        server_id, update.disabled, _changed_by(user_api_key_dict, hangarllm_changed_by)
    )
    if update.disabled and runs_local_servers_in_runner():
        await RunnerClient(runner_config()).stop_server(server_id)
    return await _apply_and_audit(control, update.disabled, user_api_key_dict, hangarllm_changed_by)


@router.post(
    "/server/{server_id}/tool/{tool_name}/control",
    description="Disable or re-enable one tool of an MCP server on all workers. Proxy admin only.",
    response_model=MCPServerControl,
)
async def set_mcp_tool_disabled(
    server_id: str,
    tool_name: str,
    update: MCPControlUpdate,
    user_api_key_dict: Annotated[UserAPIKeyAuth, Depends(_proxy_admin)],
    store: MCPServerControlRepositoryDep,
    hangarllm_changed_by: Annotated[str | None, Header()] = None,
) -> MCPServerControl:
    controls: Final = _require_store(store)
    _require_known_server(server_id)
    control: Final = await controls.set_tool_disabled(
        server_id, tool_name, update.disabled, _changed_by(user_api_key_dict, hangarllm_changed_by)
    )
    return await _apply_and_audit(control, update.disabled, user_api_key_dict, hangarllm_changed_by)


class MCPPackageLockRequest(HangarLLMBaseModel):
    model_config = ConfigDict(frozen=True)

    egress_allow_hosts: tuple[Annotated[str, StringConstraints(pattern=_EGRESS_HOST_PATTERN)], ...] = ()


def _require_package_store(store: MCPServerPackageStore | None) -> MCPServerPackageStore:
    if store is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database not connected.")
    return store


@router.post(
    "/server/{server_id}/package",
    description=(
        "Lock the npx or uvx package of a local MCP server and set the hosts it may reach from the MCP runner "
        "sandbox. Proxy admin only."
    ),
    response_model=MCPServerPackage,
)
async def lock_mcp_server_package(
    server_id: str,
    request: MCPPackageLockRequest,
    user_api_key_dict: Annotated[UserAPIKeyAuth, Depends(_proxy_admin)],
    store: MCPServerPackageRepositoryDep,
    hangarllm_changed_by: Annotated[str | None, Header()] = None,
) -> MCPServerPackage:
    packages: Final = _require_package_store(store)
    server: Final = _require_known_server(server_id)
    if server.transport != MCPTransport.stdio:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Only local (stdio) MCP servers have a package."
        )
    launch: Final = parse_launch_command(server.command, server.args)
    runner: Final = RunnerClient(runner_config())
    lock: Final = await runner.lock(launch.package)
    saved: Final = await packages.save_package(
        MCPServerPackage(
            server_id=server_id, package=launch.package, lock=lock, egress_allow_hosts=request.egress_allow_hosts
        ),
        _changed_by(user_api_key_dict, hangarllm_changed_by),
    )
    await runner.stop_server(server_id)
    await create_object_audit_log(
        object_id=server_id,
        action="updated",
        hangarllm_changed_by=hangarllm_changed_by,
        user_api_key_dict=user_api_key_dict,
        hangarllm_proxy_admin_name=HANGARLLM_PROXY_ADMIN_NAME,
        table_name=HangarllmTableNames.MCP_SERVER_PACKAGE_TABLE_NAME,
        after_value=saved.model_dump_json(include={"server_id", "package", "egress_allow_hosts"}),
    )
    return saved


@router.get(
    "/server/{server_id}/package",
    description="The locked package and egress hosts of a local MCP server. Proxy admin only.",
    response_model=MCPServerPackage | None,
)
async def get_mcp_server_package(
    server_id: str,
    _: Annotated[UserAPIKeyAuth, Depends(_proxy_admin)],
    store: MCPServerPackageRepositoryDep,
) -> MCPServerPackage | None:
    return await _require_package_store(store).get_package(server_id)
