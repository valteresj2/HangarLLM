import asyncio
from collections.abc import Awaitable, Callable, Iterable, Mapping
from types import MappingProxyType
from typing import Final

from hangarllm._logging import verbose_proxy_logger
from hangarllm.models.mcp_server_control import MCPServerControl

MCP_SERVER_CONTROL_POLL_SECONDS: Final = 2.0
MCP_DISABLED_ERROR_CODE: Final = -32003
MCP_DISABLED_MESSAGE: Final = "Disabled by an administrator"

ControlLoader = Callable[[], Awaitable[tuple[MCPServerControl, ...]]]


def _by_server(controls: Iterable[MCPServerControl]) -> Mapping[str, MCPServerControl]:
    return MappingProxyType({control.server_id: control for control in controls})


class MCPServerControls:
    """This worker's copy of the admin disable flags.

    Every worker polls the control table, so a flag set on one worker reaches the others within
    one poll interval without depending on Redis. The worker that handles the change applies it
    at once with ``apply``.
    """

    def __init__(self, poll_seconds: float = MCP_SERVER_CONTROL_POLL_SECONDS) -> None:
        self._controls: Mapping[str, MCPServerControl] = MappingProxyType({})
        self._poll_seconds = poll_seconds
        self._poller: asyncio.Task[None] | None = None

    def replace(self, controls: Iterable[MCPServerControl]) -> None:
        self._controls = _by_server(controls)

    def apply(self, control: MCPServerControl) -> None:
        self._controls = _by_server((*self._controls.values(), control))

    def forget(self, server_id: str) -> None:
        self._controls = _by_server(c for c in self._controls.values() if c.server_id != server_id)

    def is_server_disabled(self, server_id: str) -> bool:
        control: Final = self._controls.get(server_id)
        return control is not None and control.disabled

    def disabled_tools(self, server_id: str) -> frozenset[str]:
        control: Final = self._controls.get(server_id)
        return frozenset() if control is None else control.disabled_tools

    def is_tool_disabled(self, server_id: str, tool_name: str) -> bool:
        control: Final = self._controls.get(server_id)
        return control is not None and (control.disabled or tool_name in control.disabled_tools)

    async def refresh(self, load: ControlLoader) -> None:
        try:
            self.replace(await load())
        except Exception as e:  # noqa: BLE001  # a failed poll keeps the last known flags until the next one
            verbose_proxy_logger.warning("MCP server control refresh failed, keeping the last known flags: %s", e)

    async def _poll(self, load: ControlLoader) -> None:
        while True:
            await self.refresh(load)
            await asyncio.sleep(self._poll_seconds)

    def start_polling(self, load: ControlLoader) -> None:
        if self._poller is not None and not self._poller.done():
            return
        self._poller = asyncio.create_task(self._poll(load), name="mcp-server-control-poll")

    async def stop_polling(self) -> None:
        poller: Final = self._poller
        self._poller = None
        if poller is None:
            return
        poller.cancel()
        await asyncio.gather(poller, return_exceptions=True)


mcp_server_controls: Final = MCPServerControls()
