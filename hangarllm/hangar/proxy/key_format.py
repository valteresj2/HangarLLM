"""Virtual key format: a distinctive prefix plus a checksum, so leaked keys can be found by scanners.

``hgr_`` + 32 random base62 characters + a 6 character base62 CRC32 of those characters. The checksum
lets a scanner discard random look-alikes offline, without asking the gateway.
"""

import secrets
import string
import zlib
from typing import Final

from hangarllm.constants import VIRTUAL_KEY_PREFIX

_ALPHABET: Final = string.digits + string.ascii_uppercase + string.ascii_lowercase
_BODY_LENGTH: Final = 32
_CHECKSUM_LENGTH: Final = 6


def _checksum(body: str) -> str:
    value: Final = zlib.crc32(body.encode())
    digits: Final = tuple(_ALPHABET[(value // 62**power) % 62] for power in range(_CHECKSUM_LENGTH))
    return "".join(reversed(digits))


def generate_virtual_key() -> str:
    body: Final = "".join(secrets.choice(_ALPHABET) for _ in range(_BODY_LENGTH))
    return f"{VIRTUAL_KEY_PREFIX}{body}{_checksum(body)}"


def has_valid_checksum(key: str) -> bool:
    if not key.startswith(VIRTUAL_KEY_PREFIX):
        return False
    payload: Final = key[len(VIRTUAL_KEY_PREFIX) :]
    if len(payload) != _BODY_LENGTH + _CHECKSUM_LENGTH or any(c not in _ALPHABET for c in payload):
        return False
    return secrets.compare_digest(_checksum(payload[:_BODY_LENGTH]), payload[_BODY_LENGTH:])
