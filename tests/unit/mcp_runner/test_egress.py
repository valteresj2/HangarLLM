import asyncio
import contextlib
from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from typing import Final

import pytest

from hangarllm.mcp_runner.egress import EgressProxy, is_allowed, parse_allow_list

ALLOW: Final = parse_allow_list(("api.github.com", "*.example.com", "files.example.org:8443"))
CRLF: Final = "\r\n"


@pytest.mark.parametrize(
    ("host", "port", "allowed"),
    [
        ("api.github.com", 443, True),
        ("API.GitHub.com.", 443, True),
        ("api.github.com", 80, False),
        ("evil-api.github.com", 443, False),
        ("github.com", 443, False),
        ("deep.sub.example.com", 443, True),
        ("example.com", 443, False),
        ("example.com.attacker.net", 443, False),
        ("files.example.org", 8443, True),
        ("files.example.org", 443, False),
        ("140.82.112.6", 443, False),
        ("[::1]", 443, False),
    ],
)
def test_only_listed_host_names_and_ports_are_allowed(host: str, port: int, allowed: bool):
    assert is_allowed(host, port, ALLOW) is allowed


def _connect(target: str, body: str = "") -> bytes:
    return f"CONNECT {target} HTTP/1.1{CRLF}{CRLF}{body}".encode()


async def _echo(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    writer.write(b"echo:" + await reader.read(100))
    await writer.drain()
    writer.close()


@contextlib.asynccontextmanager
async def _echo_server() -> AsyncIterator[int]:
    server: Final = await asyncio.start_server(_echo, "127.0.0.1", 0)
    try:
        yield server.sockets[0].getsockname()[1]
    finally:
        server.close()


async def _through_proxy(proxy: EgressProxy, socket_dir: Path, request: bytes) -> bytes:
    socket_path: Final = str(socket_dir / "egress.sock")
    server: Final = await proxy.serve(socket_path)
    try:
        reader, writer = await asyncio.open_unix_connection(socket_path)
        writer.write(request)
        await writer.drain()
        answer: Final = await asyncio.wait_for(reader.read(), timeout=5)
        writer.close()
        return answer
    finally:
        server.close()


def _resolver(addresses: Sequence[str]):
    async def resolve(host: str, port: int) -> Sequence[str]:
        return addresses

    return resolve


@pytest.mark.asyncio
async def test_an_unlisted_host_is_refused(socket_dir: Path):
    proxy: Final = EgressProxy("srv-1", ALLOW, resolve=_resolver(("140.82.112.6",)))

    answer: Final = await _through_proxy(proxy, socket_dir, _connect("attacker.net:443"))

    assert answer.startswith(b"HTTP/1.1 403"), answer


@pytest.mark.asyncio
async def test_a_listed_host_that_resolves_to_a_private_address_is_refused(socket_dir: Path):
    proxy: Final = EgressProxy(
        "srv-1", parse_allow_list(("internal.example.com",)), resolve=_resolver(("127.0.0.1", "10.0.0.5"))
    )

    answer: Final = await _through_proxy(proxy, socket_dir, _connect("internal.example.com:443"))

    assert answer.startswith(b"HTTP/1.1 403"), answer


@pytest.mark.asyncio
async def test_only_connect_requests_are_relayed(socket_dir: Path):
    proxy: Final = EgressProxy("srv-1", ALLOW)

    answer: Final = await _through_proxy(proxy, socket_dir, f"GET http://api.github.com/ HTTP/1.1{CRLF}{CRLF}".encode())

    assert answer.startswith(b"HTTP/1.1 405"), answer


@pytest.mark.asyncio
async def test_an_allowed_connect_relays_bytes_both_ways(socket_dir: Path):
    async with _echo_server() as echo_port:
        proxy: Final = EgressProxy(
            "srv-1",
            parse_allow_list((f"api.example.com:{echo_port}",)),
            resolve=_resolver(("127.0.0.1",)),
            address_allowed=lambda address: address == "127.0.0.1",
        )
        answer: Final = await _through_proxy(proxy, socket_dir, _connect(f"api.example.com:{echo_port}", "hello"))

    assert answer.startswith(b"HTTP/1.1 200"), answer
    assert answer.endswith(b"echo:hello"), answer
