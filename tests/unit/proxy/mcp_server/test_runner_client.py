import json
from typing import Final

import httpx
import pytest
from fastapi import HTTPException

from hangarllm.mcp_runner.models import PackageRef, instance_key
from hangarllm.models.mcp_server_package import MCPServerPackage
from hangarllm.proxy.mcp_server.runner_client import (
    RunnerClient,
    RunnerConfig,
    parse_launch_command,
    require_locked_package,
)


@pytest.mark.parametrize(
    ("command", "args", "launcher", "name", "version", "rest"),
    [
        (
            "npx",
            ["-y", "@modelcontextprotocol/server-everything@2025.9.25", "stdio"],
            "npx",
            "@modelcontextprotocol/server-everything",
            "2025.9.25",
            ("stdio",),
        ),
        (
            "/usr/bin/npx",
            ["mcp-remote@0.1.29", "https://example.com/mcp"],
            "npx",
            "mcp-remote",
            "0.1.29",
            ("https://example.com/mcp",),
        ),
        ("uvx", ["mcp-server-fetch==2025.4.7"], "uvx", "mcp-server-fetch", "2025.4.7", ()),
        (
            "uvx",
            ["--python", "3.13", "mcp-server-time==2025.9.25", "--local-timezone", "UTC"],
            "uvx",
            "mcp-server-time",
            "2025.9.25",
            ("--local-timezone", "UTC"),
        ),
    ],
)
def test_the_pinned_package_and_its_own_arguments_are_read_from_the_command(
    command: str, args: list[str], launcher: str, name: str, version: str, rest: tuple[str, ...]
):
    launch: Final = parse_launch_command(command, args)

    assert (launch.package.launcher, launch.package.name, launch.package.version) == (launcher, name, version)
    assert launch.args == rest


@pytest.mark.parametrize(
    ("command", "args"),
    [
        ("npx", ["-y", "@modelcontextprotocol/server-everything"]),
        ("uvx", ["mcp-server-fetch"]),
        ("python", ["-m", "my_server"]),
        ("docker", ["run", "-i", "mcp/fetch"]),
    ],
)
def test_unpinned_packages_and_other_launchers_are_refused(command: str, args: list[str]):
    with pytest.raises(HTTPException) as refused:
        parse_launch_command(command, args)

    assert refused.value.status_code == 409


def _stored(version: str = "1.0.0") -> MCPServerPackage:
    return MCPServerPackage(
        server_id="srv-1",
        package=PackageRef(launcher="npx", name="some-server", version=version),
        lock="{}",
        egress_allow_hosts=("api.example.com",),
    )


def test_a_server_whose_command_moved_to_another_version_must_be_locked_again():
    launch: Final = parse_launch_command("npx", ["some-server@2.0.0"])

    with pytest.raises(HTTPException) as refused:
        require_locked_package("srv-1", _stored("1.0.0"), launch)
    with pytest.raises(HTTPException) as missing:
        require_locked_package("srv-1", None, launch)

    assert refused.value.status_code == 409
    assert missing.value.status_code == 409
    assert require_locked_package("srv-1", _stored("2.0.0"), launch).package.version == "2.0.0"


def test_each_credential_binding_gets_its_own_instance():
    assert instance_key("srv-1", {"TOKEN": "alice"}) != instance_key("srv-1", {"TOKEN": "bob"})
    assert instance_key("srv-1", {"A": "1", "B": "2"}) == instance_key("srv-1", {"B": "2", "A": "1"})
    assert instance_key("srv-1", {}) != instance_key("srv-2", {})


@pytest.mark.asyncio
async def test_registering_sends_the_binding_to_its_own_instance_and_returns_its_url():
    seen: list[httpx.Request] = []  # mutable-ok: records the fake runner's requests

    def runner(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(204)

    client: Final = RunnerClient(RunnerConfig(url="http://runner:4100", token="t" * 40), httpx.MockTransport(runner))
    launch: Final = parse_launch_command("npx", ["some-server@1.0.0", "--verbose"])

    url: Final = await client.register(_stored(), launch, {"TOKEN": "alice"})

    key: Final = instance_key("srv-1", {"TOKEN": "alice"})
    assert url == f"http://runner:4100/v1/instances/{key}/mcp"
    assert seen[0].method == "PUT" and seen[0].url.path == f"/v1/instances/{key}"
    assert seen[0].headers["authorization"] == f"Bearer {'t' * 40}"
    body: Final = json.loads(seen[0].content)
    assert body["env"] == {"TOKEN": "alice"}
    assert body["args"] == ["--verbose"]
    assert body["egress_allow_hosts"] == ["api.example.com"]


@pytest.mark.asyncio
async def test_an_unreachable_runner_is_reported_as_unavailable():
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    client: Final = RunnerClient(RunnerConfig(url="http://runner:4100", token="t" * 40), httpx.MockTransport(down))

    with pytest.raises(HTTPException) as unavailable:
        await client.register(_stored(), parse_launch_command("npx", ["some-server@1.0.0"]), {})

    assert unavailable.value.status_code == 503
