import hmac
import os
import re
import shutil
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Final

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi import Path as PathParam
from pydantic import ConfigDict
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Mount
from starlette.types import Receive, Scope, Send

from hangarllm.mcp_runner.models import (
    INSTANCE_KEY_PATTERN,
    InstanceInfo,
    InstanceSpec,
    LockRequest,
    LockResult,
    instance_key,
)
from hangarllm.mcp_runner.packages import PackageCache, PackageError, lock_package
from hangarllm.mcp_runner.sessions import SessionBridge
from hangarllm.types.llms.base import HangarLLMBaseModel


class RunnerSettings(HangarLLMBaseModel):
    model_config = ConfigDict(frozen=True)

    token: str
    data_dir: Path
    bwrap: str
    npm: str
    uv: str
    python: str


def _read_token() -> str:
    token_file: Final = os.environ.get("HANGARLLM_MCP_RUNNER_TOKEN_FILE")
    token: Final = (
        Path(token_file).read_text().strip() if token_file else os.environ.get("HANGARLLM_MCP_RUNNER_TOKEN", "")
    )
    if len(token) < 32:
        raise RuntimeError("HANGARLLM_MCP_RUNNER_TOKEN (or _FILE) must hold at least 32 characters")
    return token


def settings_from_env() -> RunnerSettings:
    return RunnerSettings(
        token=_read_token(),
        data_dir=Path(os.environ.get("HANGARLLM_MCP_RUNNER_DATA_DIR", "/var/lib/mcp-runner")),
        bwrap=shutil.which("bwrap") or "/usr/bin/bwrap",
        npm=shutil.which("npm") or "/usr/bin/npm",
        uv=shutil.which("uv") or "/usr/bin/uv",
        python=os.environ.get("HANGARLLM_MCP_RUNNER_PYTHON", "/usr/bin/python3.13"),
    )


_INSTANCE_MCP_PATH: Final = re.compile(r"/v1/instances/([0-9a-f]{64})/mcp/?$")


class _InstanceRoutes:
    """ASGI app for /v1/instances/{key}/mcp, which streams MCP and so cannot be a FastAPI route."""

    def __init__(self, bridge: SessionBridge, token: str) -> None:
        self._bridge = bridge
        self._token = token

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        request: Final = Request(scope, receive)
        match: Final = _INSTANCE_MCP_PATH.search(scope["path"])
        authorized: Final = hmac.compare_digest(request.headers.get("authorization", ""), f"Bearer {self._token}")
        if not authorized:
            await Response(status_code=status.HTTP_401_UNAUTHORIZED)(scope, receive, send)
            return
        if match is None:
            await Response(status_code=status.HTTP_404_NOT_FOUND)(scope, receive, send)
            return
        await self._bridge.handle(match.group(1), scope, receive, send)


def build_app(settings: RunnerSettings) -> FastAPI:
    bridge: Final = SessionBridge(bwrap=settings.bwrap, socket_dir=settings.data_dir / "sockets")
    packages: Final = PackageCache(
        root=settings.data_dir / "packages", npm=settings.npm, uv=settings.uv, python=settings.python
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        async with bridge.running():
            yield

    def require_token(authorization: Annotated[str, Header()] = "") -> None:
        if not hmac.compare_digest(authorization, f"Bearer {settings.token}"):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    app: Final = FastAPI(
        title="HangarLLM MCP runner",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.post("/v1/packages/lock", response_model=LockResult, dependencies=[Depends(require_token)])
    async def lock(request: LockRequest) -> LockResult:
        try:
            lock_text: Final = await lock_package(request.package, settings.npm, settings.uv)
        except PackageError as error:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
        return LockResult(package=request.package, lock=lock_text)

    @app.put("/v1/instances/{key}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_token)])
    async def register(key: Annotated[str, PathParam(pattern=INSTANCE_KEY_PATTERN)], spec: InstanceSpec) -> None:
        if not hmac.compare_digest(key, instance_key(spec.server_id, spec.env)):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="instance key does not match the spec")
        try:
            installed: Final = await packages.install(spec.package, spec.lock)
        except PackageError as error:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
        bridge.register(key, spec, installed)

    @app.delete("/v1/instances/{key}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_token)])
    async def remove(key: str) -> None:
        bridge.remove(key)

    @app.delete(
        "/v1/servers/{server_id}/instances",
        status_code=status.HTTP_204_NO_CONTENT,
        dependencies=[Depends(require_token)],
    )
    async def remove_server(server_id: str) -> None:
        bridge.remove_server(server_id)

    @app.get("/v1/instances", response_model=tuple[InstanceInfo, ...], dependencies=[Depends(require_token)])
    async def list_instances() -> tuple[InstanceInfo, ...]:
        return bridge.instances()

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.router.routes.append(Mount("/v1/instances", app=_InstanceRoutes(bridge, settings.token)))
    return app
