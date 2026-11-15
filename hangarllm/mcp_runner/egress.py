"""The only way out of a sandbox: an HTTP CONNECT proxy on a Unix socket that admits listed hosts."""

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Final

from hangarllm._logging import verbose_proxy_logger

DEFAULT_PORT: Final = 443
_MAX_HEADER_BYTES: Final = 16_384
_CONNECT_TIMEOUT_SECONDS: Final = 15.0

Resolver = Callable[[str, int], Awaitable[Sequence[str]]]


@dataclass(frozen=True, slots=True)
class AllowedHost:
    host: str
    port: int
    any_subdomain: bool


def parse_allow_list(entries: Sequence[str]) -> tuple[AllowedHost, ...]:
    def parse(entry: str) -> AllowedHost:
        host, _, port = entry.strip().lower().partition(":")
        wildcard: Final = host.startswith("*.")
        return AllowedHost(
            host=host[2:] if wildcard else host, port=int(port) if port else DEFAULT_PORT, any_subdomain=wildcard
        )

    return tuple(parse(entry) for entry in entries if entry.strip())


def _is_ip_literal(host: str) -> bool:
    try:
        ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return False
    return True


def is_allowed(host: str, port: int, allow_list: Sequence[AllowedHost]) -> bool:
    """Hosts are matched by name, never by address, so a listed name cannot be swapped for an IP."""
    name: Final = host.lower().rstrip(".")
    if _is_ip_literal(name):
        return False
    return any(
        entry.port == port and (name.endswith("." + entry.host) if entry.any_subdomain else name == entry.host)
        for entry in allow_list
    )


def is_public_address(address: str) -> bool:
    return ipaddress.ip_address(address).is_global


async def resolve_host(host: str, port: int) -> Sequence[str]:
    infos: Final = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return tuple(str(info[4][0]) for info in infos)


def _parse_connect(head: bytes) -> tuple[str, int] | None:
    request_line: Final = head.split(b"\r\n", 1)[0].decode("latin-1")
    parts: Final = request_line.split(" ")
    if len(parts) != 3 or parts[0] != "CONNECT":
        return None
    host, _, port = parts[1].rpartition(":")
    if not host or not port.isdigit():
        return None
    return host.strip("[]"), int(port)


async def _splice(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while chunk := await reader.read(65_536):
            writer.write(chunk)
            await writer.drain()
    finally:
        writer.close()


class EgressProxy:
    def __init__(
        self,
        server_id: str,
        allow_list: Sequence[AllowedHost],
        resolve: Resolver = resolve_host,
        address_allowed: Callable[[str], bool] = is_public_address,
    ) -> None:
        self._server_id = server_id
        self._allow_list = tuple(allow_list)
        self._resolve = resolve
        self._address_allowed = address_allowed

    async def _refuse(self, writer: asyncio.StreamWriter, status: str, host: str, port: int) -> None:
        verbose_proxy_logger.warning(
            "MCP runner refused egress for server %s to %s:%s (%s)", self._server_id, host, port, status
        )
        writer.write(f"HTTP/1.1 {status}\r\nContent-Length: 0\r\n\r\n".encode())
        await writer.drain()
        writer.close()

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            head: Final = await reader.readuntil(b"\r\n\r\n")
        except (asyncio.IncompleteReadError, asyncio.LimitOverrunError):
            writer.close()
            return
        target: Final = _parse_connect(head[:_MAX_HEADER_BYTES])
        if target is None:
            await self._refuse(writer, "405 Method Not Allowed", "?", 0)
            return
        host, port = target
        if not is_allowed(host, port, self._allow_list):
            await self._refuse(writer, "403 Forbidden", host, port)
            return
        addresses: Final = tuple(a for a in await self._resolve(host, port) if self._address_allowed(a))
        if not addresses:
            await self._refuse(writer, "403 Forbidden", host, port)
            return
        try:
            upstream_reader, upstream_writer = await asyncio.wait_for(
                asyncio.open_connection(addresses[0], port), timeout=_CONNECT_TIMEOUT_SECONDS
            )
        except (OSError, TimeoutError):
            await self._refuse(writer, "502 Bad Gateway", host, port)
            return
        writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        await writer.drain()
        await asyncio.gather(_splice(reader, upstream_writer), _splice(upstream_reader, writer), return_exceptions=True)

    async def serve(self, socket_path: str) -> asyncio.Server:
        return await asyncio.start_unix_server(self.handle, path=socket_path, limit=_MAX_HEADER_BYTES)
