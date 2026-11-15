import asyncio
from collections.abc import Iterator
from typing import Final

import pytest
from mcp.shared.exceptions import MCPError
from mcp.types import Tool

from hangarllm.models.mcp_server_control import MCPServerControl
from hangarllm.proxy.mcp_server.mcp_server_manager import MCPServerManager
from hangarllm.proxy.mcp_server.operations import filter_tools_by_allowed_tools
from hangarllm.proxy.mcp_server.server_controls import MCP_DISABLED_ERROR_CODE, MCPServerControls, mcp_server_controls
from hangarllm.types.mcp import MCPAuth, MCPTransport
from hangarllm.types.mcp_server.mcp_server_manager import MCPServer


class _SharedControlTable:
    """Stands in for the control table that every worker reads."""

    def __init__(self) -> None:
        self.rows: dict[str, MCPServerControl] = {}  # mutable-ok: fake table state
        self.fail = False

    async def list_controls(self) -> tuple[MCPServerControl, ...]:
        if self.fail:
            raise ConnectionError("database unreachable")
        return tuple(self.rows.values())

    def write(self, control: MCPServerControl) -> None:
        self.rows[control.server_id] = control


def _server(server_id: str = "srv-1") -> MCPServer:
    return MCPServer(
        server_id=server_id,
        name="github",
        server_name="github",
        url="https://example.com/mcp",
        transport=MCPTransport.http,
        auth_type=MCPAuth.none,
    )


@pytest.mark.asyncio
async def test_a_tool_disabled_on_one_worker_is_refused_by_another_after_its_next_refresh():
    table: Final = _SharedControlTable()
    handling_worker: Final = MCPServerControls()
    other_worker: Final = MCPServerControls()
    await other_worker.refresh(table.list_controls)

    control: Final = MCPServerControl(server_id="srv-1", disabled_tools=frozenset({"delete_repo"}))
    table.write(control)
    handling_worker.apply(control)
    assert handling_worker.is_tool_disabled("srv-1", "delete_repo")
    assert not other_worker.is_tool_disabled("srv-1", "delete_repo")

    await other_worker.refresh(table.list_controls)

    assert other_worker.is_tool_disabled("srv-1", "delete_repo")
    assert not other_worker.is_tool_disabled("srv-1", "list_repos")
    assert not other_worker.is_tool_disabled("srv-2", "delete_repo")


@pytest.mark.asyncio
async def test_disabling_a_server_disables_every_tool_until_it_is_enabled_again():
    controls: Final = MCPServerControls()
    controls.apply(MCPServerControl(server_id="srv-1", disabled=True))
    assert controls.is_server_disabled("srv-1")
    assert controls.is_tool_disabled("srv-1", "any_tool")

    controls.apply(MCPServerControl(server_id="srv-1", disabled=False))

    assert not controls.is_tool_disabled("srv-1", "any_tool")


@pytest.mark.asyncio
async def test_a_failed_refresh_keeps_the_last_known_flags():
    table: Final = _SharedControlTable()
    table.write(MCPServerControl(server_id="srv-1", disabled=True))
    controls: Final = MCPServerControls()
    await controls.refresh(table.list_controls)

    table.fail = True
    await controls.refresh(table.list_controls)

    assert controls.is_server_disabled("srv-1")


@pytest.mark.asyncio
async def test_polling_picks_up_a_flag_written_by_another_worker():
    table: Final = _SharedControlTable()
    controls: Final = MCPServerControls(poll_seconds=0.01)
    controls.start_polling(table.list_controls)
    try:
        table.write(MCPServerControl(server_id="srv-1", disabled=True))
        await asyncio.wait_for(_until(lambda: controls.is_server_disabled("srv-1")), timeout=2)
    finally:
        await controls.stop_polling()


async def _until(condition) -> None:
    while not condition():
        await asyncio.sleep(0.01)


@pytest.fixture
def global_controls() -> Iterator[MCPServerControls]:
    yield mcp_server_controls
    mcp_server_controls.forget("srv-1")


@pytest.mark.asyncio
async def test_calling_a_disabled_tool_fails_with_the_disabled_error_before_reaching_the_server(
    global_controls: MCPServerControls,
):
    manager: Final = MCPServerManager()
    global_controls.apply(MCPServerControl(server_id="srv-1", disabled_tools=frozenset({"delete_repo"})))

    with pytest.raises(MCPError) as refused:
        await manager.pre_call_tool_check(
            name="delete_repo",
            arguments={},
            server_name="github",
            user_api_key_auth=None,
            proxy_logging_obj=None,
            server=_server(),
        )

    assert refused.value.error.code == MCP_DISABLED_ERROR_CODE
    assert (
        await manager.pre_call_tool_check(
            name="list_repos",
            arguments={},
            server_name="github",
            user_api_key_auth=None,
            proxy_logging_obj=None,
            server=_server(),
        )
        == {}
    )


def test_disabled_tools_are_left_out_of_the_tool_list(global_controls: MCPServerControls):
    tools: Final = [
        Tool(name="github-delete_repo", inputSchema={"type": "object"}),
        Tool(name="github-list_repos", inputSchema={"type": "object"}),
    ]
    global_controls.apply(MCPServerControl(server_id="srv-1", disabled_tools=frozenset({"delete_repo"})))

    listed: Final = filter_tools_by_allowed_tools(tools, _server())

    assert [tool.name for tool in listed] == ["github-list_repos"]


def test_a_disabled_server_lists_no_tools(global_controls: MCPServerControls):
    tools: Final = [Tool(name="github-list_repos", inputSchema={"type": "object"})]
    global_controls.apply(MCPServerControl(server_id="srv-1", disabled=True))

    assert filter_tools_by_allowed_tools(tools, _server()) == []
