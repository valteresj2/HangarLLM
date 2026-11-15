"""Each MCP session the gateway opens on an instance gets its own sandboxed process.

A stdio MCP server speaks to one client, so a session is the unit that starts and stops a process. The
instance key decides which package, environment and egress list the process gets.
"""

import contextlib
import tempfile
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, Protocol
from uuid import uuid4

import anyio
from anyio.abc import TaskGroup, TaskStatus
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.server.streamable_http import StreamableHTTPServerTransport
from starlette.responses import JSONResponse
from starlette.types import Receive, Scope, Send

from hangarllm._logging import verbose_proxy_logger
from hangarllm.mcp_runner.egress import EgressProxy, parse_allow_list
from hangarllm.mcp_runner.models import InstanceInfo, InstanceSpec
from hangarllm.mcp_runner.packages import InstalledPackage
from hangarllm.mcp_runner.sandbox import bwrap_argv

_SESSION_HEADER: Final = "mcp-session-id"


class _Stream(Protocol):
    def __aiter__(self) -> AsyncIterator[object]: ...


class _Sink(Protocol):
    async def send(self, item: object, /) -> None: ...


async def _pump(source: _Stream, sink: _Sink, session_scope: anyio.CancelScope) -> None:
    """Forward messages until the source ends, then end the whole session.

    Ending the session matters because a stdio MCP server often keeps running after its stdin closes, so
    waiting for its stdout to end would keep the sandbox alive forever. Leaving ``stdio_client`` is what
    stops the process.
    """
    try:
        async for message in source:
            if isinstance(message, Exception):
                verbose_proxy_logger.warning("MCP runner dropped an unreadable message: %s", message)
                continue
            await sink.send(message)
    finally:
        session_scope.cancel()


@dataclass(slots=True)
class _Session:
    instance_key: str
    server_id: str
    transport: StreamableHTTPServerTransport


@dataclass(slots=True)
class _Instance:
    spec: InstanceSpec
    package: InstalledPackage
    sessions: dict[str, _Session] = field(default_factory=dict)  # mutable-ok: live sessions of this instance


class SessionBridge:
    def __init__(self, bwrap: str, socket_dir: Path) -> None:
        self._bwrap = bwrap
        self._socket_dir = socket_dir
        self._instances: dict[str, _Instance] = {}  # mutable-ok: registered instances by key
        self._task_group: TaskGroup | None = None

    @contextlib.asynccontextmanager
    async def running(self) -> AsyncIterator[None]:
        self._socket_dir.mkdir(parents=True, exist_ok=True)
        async with anyio.create_task_group() as task_group:
            self._task_group = task_group
            try:
                yield
            finally:
                task_group.cancel_scope.cancel()
                self._task_group = None

    def register(self, key: str, spec: InstanceSpec, package: InstalledPackage) -> None:
        existing: Final = self._instances.get(key)
        sessions: Final = existing.sessions if existing is not None and existing.spec == spec else {}
        if existing is not None and existing.spec != spec:
            self._terminate_sessions(existing)
        self._instances[key] = _Instance(spec=spec, package=package, sessions=sessions)

    def instances(self) -> tuple[InstanceInfo, ...]:
        return tuple(
            InstanceInfo(instance_key=key, server_id=instance.spec.server_id, sessions=len(instance.sessions))
            for key, instance in self._instances.items()
        )

    def _terminate_sessions(self, instance: _Instance) -> None:
        for session in tuple(instance.sessions.values()):
            if self._task_group is not None:
                self._task_group.start_soon(session.transport.terminate)
        instance.sessions.clear()

    def remove(self, key: str) -> bool:
        instance: Final = self._instances.pop(key, None)
        if instance is None:
            return False
        self._terminate_sessions(instance)
        return True

    def remove_server(self, server_id: str) -> int:
        keys: Final = tuple(key for key, instance in self._instances.items() if instance.spec.server_id == server_id)
        return sum(self.remove(key) for key in keys)

    async def _run_process(
        self, instance: _Instance, session_id: str, *, task_status: TaskStatus[None] = anyio.TASK_STATUS_IGNORED
    ) -> None:
        session: Final = instance.sessions[session_id]
        socket_path: Final = Path(tempfile.mkdtemp(dir=self._socket_dir)) / "egress.sock"
        proxy: Final = EgressProxy(instance.spec.server_id, parse_allow_list(instance.spec.egress_allow_hosts))
        egress_server: Final = await proxy.serve(str(socket_path))
        argv: Final = bwrap_argv(
            bwrap=self._bwrap,
            package_dir=instance.package.directory,
            egress_socket=socket_path,
            entry=(*instance.package.entry, *instance.spec.args),
            env=instance.spec.env,
        )
        try:
            async with session.transport.connect() as (http_read, http_write):
                task_status.started()
                async with stdio_client(StdioServerParameters(command=argv[0], args=list(argv[1:]), env={})) as (
                    process_read,
                    process_write,
                ):
                    idle_scope: Final = session.transport.idle_scope or anyio.CancelScope()
                    with idle_scope:
                        async with anyio.create_task_group() as pumps:
                            pumps.start_soon(_pump, http_read, process_write, pumps.cancel_scope)
                            pumps.start_soon(_pump, process_read, http_write, pumps.cancel_scope)
        except Exception:
            verbose_proxy_logger.exception(
                "MCP runner session %s for server %s ended with an error", session_id, instance.spec.server_id
            )
        finally:
            instance.sessions.pop(session_id, None)
            egress_server.close()
            with contextlib.suppress(OSError):
                socket_path.unlink()
                socket_path.parent.rmdir()
            if not session.transport.is_terminated:
                with anyio.CancelScope(shield=True):
                    await session.transport.terminate()

    async def handle(self, key: str, scope: Scope, receive: Receive, send: Send) -> None:
        instance: Final = self._instances.get(key)
        if instance is None or self._task_group is None:
            await JSONResponse({"error": "unknown instance"}, status_code=404)(scope, receive, send)
            return
        headers: Final[Mapping[bytes, bytes]] = dict(scope.get("headers") or ())
        session_id: Final = headers.get(_SESSION_HEADER.encode(), b"").decode() or None
        if session_id is not None:
            session: Final = instance.sessions.get(session_id)
            if session is None:
                await JSONResponse({"error": "Session not found"}, status_code=404)(scope, receive, send)
                return
            await session.transport.handle_request(scope, receive, send)
            return
        new_id: Final = uuid4().hex
        instance.sessions[new_id] = _Session(
            instance_key=key,
            server_id=instance.spec.server_id,
            transport=StreamableHTTPServerTransport(
                mcp_session_id=new_id, idle_timeout=instance.spec.idle_timeout_seconds
            ),
        )
        await self._task_group.start(self._run_process, instance, new_id)
        started: Final = instance.sessions.get(new_id)
        if started is None:
            await JSONResponse({"error": "session ended before it started"}, status_code=502)(scope, receive, send)
            return
        await started.transport.handle_request(scope, receive, send)
