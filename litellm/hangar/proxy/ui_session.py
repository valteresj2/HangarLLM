"""Keep the dashboard's session key out of reach of browser JavaScript.

The dashboard reads the ``token`` cookie to build its Authorization headers, so anything in that
cookie is one XSS away from being stolen. The cookie now carries a placeholder instead of a key.
The real session JWT travels sealed in an HttpOnly cookie, and this middleware swaps the
placeholder for the real key on each request. Script running in the page can still act during the
session, but it can no longer carry a working key away.
"""

import base64
import hashlib
import hmac
import os
from collections.abc import Mapping
from typing import Final

import jwt
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from starlette.types import ASGIApp, Receive, Scope, Send

SESSION_COOKIE: Final = "hangar_session"
BROWSER_SESSION_KEY: Final = "hangar-ui-session"
SESSION_SECRET_ENV_VAR: Final = "LITELLM_UI_SESSION_SECRET"
_SENTINEL: Final = BROWSER_SESSION_KEY.encode()
_NONCE_BYTES: Final = 12
_JWT_ALGORITHM: Final = "HS256"
_CROSS_SITE: Final = b"cross-site"


def session_secret() -> str:
    """The UI session signing secret, derived from the salt key when none is configured.

    Deriving keeps the signing secret distinct from the master key without another required setting.
    """
    explicit: Final = os.getenv(SESSION_SECRET_ENV_VAR)
    if explicit:
        return explicit
    from litellm.proxy.common_utils.encrypt_decrypt_utils import get_salt_key

    base: Final = get_salt_key()
    if not base:
        raise ValueError("A master key or salt key is required to sign UI sessions")
    return hmac.new(base.encode(), b"hangarllm-ui-session-v1", hashlib.sha256).hexdigest()


def _sealing_key() -> bytes:
    return hashlib.sha256(f"{session_secret()}:seal".encode()).digest()


def seal(value: str) -> str:
    nonce: Final = os.urandom(_NONCE_BYTES)
    sealed: Final = AESGCM(_sealing_key()).encrypt(nonce, value.encode(), None)
    # No padding: "=" would make the cookie value quoted, and quoted values do not round-trip.
    return base64.urlsafe_b64encode(nonce + sealed).decode().rstrip("=")


def unseal(value: str) -> str | None:
    try:
        raw: Final = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        return AESGCM(_sealing_key()).decrypt(raw[:_NONCE_BYTES], raw[_NONCE_BYTES:], None).decode()
    except (ValueError, InvalidTag):
        return None


def sign_session(claims: Mapping[str, object]) -> str:
    return jwt.encode(dict(claims), session_secret(), algorithm=_JWT_ALGORITHM)


def decode_session(token: str) -> dict[str, object] | None:
    try:
        return jwt.decode(token, session_secret(), algorithms=[_JWT_ALGORITHM], options={"require": ["exp"]})
    except jwt.InvalidTokenError:
        return None


def browser_session_token(session_token: str) -> str:
    """The JWT the browser may read: the same claims, with a placeholder where the key was."""
    claims: Final = decode_session(session_token)
    if claims is None:
        raise ValueError("Cannot derive a browser session from an invalid session token")
    return sign_session({**claims, "key": BROWSER_SESSION_KEY})


def session_claims(cookies: Mapping[str, str]) -> dict[str, object] | None:
    """Claims of the sealed session cookie, including the real key, or None when absent or invalid."""
    sealed: Final = cookies.get(SESSION_COOKIE)
    if not sealed:
        return None
    opened: Final = unseal(sealed)
    return None if opened is None else decode_session(opened)


def _cookies_from(headers: list[tuple[bytes, bytes]]) -> dict[str, str]:
    raw: Final = b"; ".join(value for name, value in headers if name == b"cookie").decode("latin-1")
    pairs: Final = (part.strip().partition("=") for part in raw.split(";"))
    return {name: value for name, _, value in pairs if name}


def _uses_placeholder(headers: list[tuple[bytes, bytes]]) -> bool:
    return any(name != b"cookie" and _SENTINEL in value for name, value in headers)


def _with_real_key(headers: list[tuple[bytes, bytes]], key: bytes, *, websocket: bool) -> list[tuple[bytes, bytes]]:
    if websocket:
        # The subprotocol is echoed back to the page on accept, so the key goes in a header instead.
        without_auth: Final = [(name, value) for name, value in headers if name != b"authorization"]
        return [*without_auth, (b"authorization", b"Bearer " + key)]
    return [(name, value if name == b"cookie" else value.replace(_SENTINEL, key)) for name, value in headers]


class UiSessionMiddleware:
    """Replace the browser placeholder with the session key held in the HttpOnly cookie."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            scope = self._resolved(scope)
        await self.app(scope, receive, send)

    @staticmethod
    def _resolved(scope: Scope) -> Scope:
        headers: Final = list(scope["headers"])
        if not _uses_placeholder(headers) or dict(headers).get(b"sec-fetch-site") == _CROSS_SITE:
            return scope
        claims: Final = session_claims(_cookies_from(headers))
        key: Final = None if claims is None else claims.get("key")
        if not isinstance(key, str) or not key or key == BROWSER_SESSION_KEY:
            return scope
        return {**scope, "headers": _with_real_key(headers, key.encode(), websocket=scope["type"] == "websocket")}
