"""
Standard-logging-payload enrichment.

Copies the custom ``x-*`` headers a client sent to the proxy into
``metadata.requester_custom_headers`` so observability backends (Langfuse,
Datadog, ClickHouse, S3, ...) can slice traffic by them. Credentials and
gateway-control headers are never copied.
"""

from collections.abc import Mapping
from typing import Final

from hangarllm.types.utils import StandardLoggingMetadata

# headers that carry credentials or gateway controls - never logged
_NEVER_LOG: Final = frozenset(
    {
        "x-api-key",
        "x-hangarllm-api-key",
        "x-hangarllm-api-key",
        "x-goog-api-key",
        "x-amz-security-token",
        "x-auth-token",
        "x-access-token",
        "x-csrf-token",
        "x-forwarded-authorization",
        "x-ms-client-principal",
        "x-hangarllm-disable-callbacks",
        "x-hangarllm-disable-callbacks",
    }
)
_SENSITIVE_FRAGMENTS: Final = ("token", "secret", "password", "authorization", "api-key", "apikey", "cookie")
_MAX_HEADERS: Final = 64
_MAX_VALUE_LEN: Final = 1024


def _is_loggable(name: str) -> bool:
    lowered: Final = name.lower()
    if not lowered.startswith("x-") or lowered in _NEVER_LOG:
        return False
    return not any(fragment in lowered for fragment in _SENSITIVE_FRAGMENTS)


def extract_custom_headers(headers: Mapping[str, object] | None) -> dict[str, str] | None:
    if not headers:
        return None
    picked: dict[str, str] = {}  # mutable-ok: built once, returned
    for name, value in headers.items():
        if len(picked) >= _MAX_HEADERS:
            break
        if isinstance(name, str) and isinstance(value, str) and _is_loggable(name):
            picked[name.lower()] = value[:_MAX_VALUE_LEN]
    return picked or None


class HangarLoggingPayloadSetup:
    @staticmethod
    def apply_enterprise_specific_metadata(
        standard_logging_metadata: StandardLoggingMetadata,
        proxy_server_request: Mapping[str, object] | object,
    ) -> StandardLoggingMetadata:
        if not isinstance(proxy_server_request, Mapping):
            return standard_logging_metadata
        headers: Final = proxy_server_request.get("headers")
        custom: Final = extract_custom_headers(headers if isinstance(headers, Mapping) else None)
        if custom is not None:
            standard_logging_metadata["requester_custom_headers"] = custom
        return standard_logging_metadata

    # Hangar-style alias
    apply_hangar_metadata = apply_enterprise_specific_metadata


# upstream-compatible name
StandardLoggingPayloadSetup = HangarLoggingPayloadSetup
