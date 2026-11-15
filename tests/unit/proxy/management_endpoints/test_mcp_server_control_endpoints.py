from collections.abc import Iterator
from typing import Final

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hangarllm.models.mcp_server_control import MCPServerControl
from hangarllm.proxy._types import HangarllmUserRoles, UserAPIKeyAuth
from hangarllm.proxy.auth.user_api_key_auth import user_api_key_auth
from hangarllm.proxy.deps.repositories import get_mcp_server_control_repository
from hangarllm.proxy.management_endpoints.mcp_server_control_endpoints import router
from hangarllm.proxy.mcp_server.mcp_server_manager import global_mcp_server_manager
from hangarllm.proxy.mcp_server.server_controls import mcp_server_controls
from hangarllm.types.mcp import MCPAuth, MCPTransport
from hangarllm.types.mcp_server.mcp_server_manager import MCPServer


class _ControlTable:
    def __init__(self) -> None:
        self.rows: dict[str, MCPServerControl] = {}  # mutable-ok: fake table state

    def _row(self, server_id: str) -> MCPServerControl:
        return self.rows.get(server_id, MCPServerControl(server_id=server_id))

    async def list_controls(self) -> tuple[MCPServerControl, ...]:
        return tuple(self.rows.values())

    async def set_server_disabled(self, server_id: str, disabled: bool, updated_by: str) -> MCPServerControl:
        self.rows[server_id] = self._row(server_id).model_copy(update={"disabled": disabled})
        return self.rows[server_id]

    async def set_tool_disabled(
        self, server_id: str, tool_name: str, disabled: bool, updated_by: str
    ) -> MCPServerControl:
        current: Final = self._row(server_id)
        tools: Final = current.disabled_tools | {tool_name} if disabled else current.disabled_tools - {tool_name}
        self.rows[server_id] = current.model_copy(update={"disabled_tools": frozenset(tools)})
        return self.rows[server_id]

    async def delete_control(self, server_id: str) -> None:
        self.rows.pop(server_id, None)


@pytest.fixture
def known_server() -> Iterator[MCPServer]:
    server: Final = MCPServer(
        server_id="srv-1",
        name="github",
        server_name="github",
        url="https://example.com/mcp",
        transport=MCPTransport.http,
        auth_type=MCPAuth.none,
    )
    global_mcp_server_manager.config_mcp_servers["srv-1"] = server
    yield server
    global_mcp_server_manager.config_mcp_servers.pop("srv-1", None)
    mcp_server_controls.forget("srv-1")


def _client(table: _ControlTable, role: HangarllmUserRoles) -> TestClient:
    app: Final = FastAPI()
    app.include_router(router)
    app.dependency_overrides[user_api_key_auth] = lambda: UserAPIKeyAuth(user_id="admin", user_role=role)
    app.dependency_overrides[get_mcp_server_control_repository] = lambda: table
    return TestClient(app)


def test_an_admin_disabling_a_config_defined_tool_stores_it_and_refuses_it_on_this_worker(known_server: MCPServer):
    table: Final = _ControlTable()

    response: Final = _client(table, HangarllmUserRoles.PROXY_ADMIN).post(
        "/v1/mcp/server/srv-1/tool/delete_repo/control", json={"disabled": True}
    )

    assert response.status_code == 200
    assert response.json()["disabled_tools"] == ["delete_repo"]
    assert table.rows["srv-1"].disabled_tools == frozenset({"delete_repo"})
    assert mcp_server_controls.is_tool_disabled("srv-1", "delete_repo")
    assert not mcp_server_controls.is_tool_disabled("srv-1", "list_repos")


def test_enabling_a_server_again_lets_its_tools_through(known_server: MCPServer):
    client: Final = _client(_ControlTable(), HangarllmUserRoles.PROXY_ADMIN)
    client.post("/v1/mcp/server/srv-1/control", json={"disabled": True})
    assert mcp_server_controls.is_tool_disabled("srv-1", "list_repos")

    response: Final = client.post("/v1/mcp/server/srv-1/control", json={"disabled": False})

    assert response.status_code == 200
    assert not mcp_server_controls.is_tool_disabled("srv-1", "list_repos")


def test_only_proxy_admins_can_disable(known_server: MCPServer):
    table: Final = _ControlTable()

    response: Final = _client(table, HangarllmUserRoles.INTERNAL_USER).post(
        "/v1/mcp/server/srv-1/control", json={"disabled": True}
    )

    assert response.status_code == 403
    assert table.rows == {}


def test_an_unknown_server_cannot_be_disabled():
    table: Final = _ControlTable()

    response: Final = _client(table, HangarllmUserRoles.PROXY_ADMIN).post(
        "/v1/mcp/server/missing/control", json={"disabled": True}
    )

    assert response.status_code == 404
    assert table.rows == {}
