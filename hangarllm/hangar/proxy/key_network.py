"""Per-key network restriction, read from ``metadata.allowed_ips`` on the virtual key."""

import ipaddress
from collections.abc import Mapping
from typing import Final

from fastapi import HTTPException, Request, status

from hangarllm.proxy.auth.auth_utils import get_request_ip_address

ALLOWED_IPS_FIELD: Final = "allowed_ips"
_WIDEST_PREFIX: Final = {4: 8, 6: 32}

IpNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network


class InvalidAllowedIps(ValueError):
    pass


def allowed_networks(metadata: object) -> tuple[IpNetwork, ...]:
    """The networks a key is restricted to, or () when it has none. Raises on anything unusable."""
    entries: Final = metadata.get(ALLOWED_IPS_FIELD) if isinstance(metadata, Mapping) else None
    if entries is None or entries == []:
        return ()
    if not isinstance(entries, list) or not all(isinstance(entry, str) for entry in entries):
        raise InvalidAllowedIps(ALLOWED_IPS_FIELD)
    try:
        networks: Final = tuple(ipaddress.ip_network(entry.strip(), strict=False) for entry in entries)
    except ValueError as error:
        raise InvalidAllowedIps(ALLOWED_IPS_FIELD) from error
    if any(network.prefixlen < _WIDEST_PREFIX[network.version] for network in networks):
        raise InvalidAllowedIps(ALLOWED_IPS_FIELD)
    return networks


def _address_in(networks: tuple[IpNetwork, ...], client_ip: str | None) -> bool:
    try:
        address: Final = ipaddress.ip_address(client_ip or "")
    except ValueError:
        return False
    return any(address in network for network in networks)


def enforce_key_allowed_ips(metadata: object, request: Request, general_settings: Mapping[str, object]) -> None:
    try:
        networks: tuple[IpNetwork, ...] | None = allowed_networks(metadata)
    except InvalidAllowedIps:
        networks = None
    if networks == ():
        return
    client_ip: Final = get_request_ip_address(
        request=request, use_x_forwarded_for=general_settings.get("use_x_forwarded_for") is True
    )
    if networks is None or not _address_in(networks, client_ip):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This key cannot be used from this IP address.")
