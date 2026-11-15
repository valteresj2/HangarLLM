from typing import Annotated, Final

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import ConfigDict

from hangarllm.constants import HANGARLLM_PROXY_ADMIN_NAME
from hangarllm.models.mcp_server_control import MCPServerControl, MCPServerControlStore
from hangarllm.proxy._types import HangarllmTableNames, HangarllmUserRoles, UserAPIKeyAuth
from hangarllm.proxy.auth.user_api_key_auth import user_api_key_auth
from hangarllm.proxy.deps.repositories import MCPServerControlRepositoryDep
from hangarllm.proxy.management_helpers.audit_logs import create_object_audit_log, get_audit_log_changed_by
from hangarllm.proxy.mcp_server.server_controls import mcp_server_controls
from hangarllm.types.llms.base import HangarLLMBaseModel

router: Final = APIRouter(prefix="/v1/mcp", tags=["mcp"])


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


def _require_known_server(server_id: str) -> None:
    from hangarllm.proxy.mcp_server.mcp_server_manager import global_mcp_server_manager

    if global_mcp_server_manager.get_mcp_server_by_id(server_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"MCP server {server_id} not found.")


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
