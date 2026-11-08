from collections.abc import Callable

import pytest

from hangarllm.constants import SESSION_ID_GENERATED_METADATA_KEY
from hangarllm.hangarllm_core_utils.provider_affinity import (
    add_provider_affinity_header,
    get_caller_session_id,
    get_stable_session_id,
)


@pytest.mark.parametrize("resolve", [get_stable_session_id, get_caller_session_id])
@pytest.mark.parametrize(
    ("hangarllm_params", "expected"),
    [
        ({"hangarllm_session_id": "hangarllm-session"}, "hangarllm-session"),
        ({"session_id": "direct-session"}, "direct-session"),
        ({"metadata": {"session_id": "metadata-session"}}, "metadata-session"),
        ({"hangarllm_metadata": {"session_id": "hangarllm-metadata-session"}}, "hangarllm-metadata-session"),
    ],
)
def test_session_ids(hangarllm_params: dict[str, object], expected: str, resolve: Callable[[object], str | None]) -> None:
    assert resolve(hangarllm_params) == expected


def test_get_stable_session_id_does_not_use_trace_id():
    assert get_stable_session_id({"hangarllm_trace_id": "per-request-trace"}) is None
    assert get_caller_session_id(
        {"hangarllm_session_id": "trace", "proxy_server_request": {"headers": {"x-hangarllm-trace-id": "trace"}}}
    ) is None


@pytest.mark.parametrize("resolve", [get_stable_session_id, get_caller_session_id])
@pytest.mark.parametrize("metadata_key", ["metadata", "hangarllm_metadata"])
def test_generated_sessions_are_ignored(metadata_key: str, resolve: Callable[[object], str | None]) -> None:
    assert (
        resolve(
            {
                "hangarllm_session_id": "generated-session",
                metadata_key: {
                    "session_id": "generated-session",
                    SESSION_ID_GENERATED_METADATA_KEY: True,
                },
            }
        )
        is None
    )


def test_get_stable_session_id_prefers_explicit_session_over_proxy_generated_session():
    assert (
        get_stable_session_id(
            {
                "session_id": "explicit-session",
                "hangarllm_session_id": "generated-session",
                "metadata": {
                    "session_id": "generated-session",
                    SESSION_ID_GENERATED_METADATA_KEY: True,
                },
            }
        )
        == "explicit-session"
    )


def test_add_provider_affinity_header_maps_session_id():
    headers = add_provider_affinity_header(
        headers={"Content-Type": "application/json"},
        hangarllm_params={
            "hangarllm_session_id": "session-123",
            "provider_affinity_header": "X-Conversation-Id",
        },
    )

    assert headers == {
        "Content-Type": "application/json",
        "X-Conversation-Id": "session-123",
    }


def test_add_provider_affinity_header_preserves_explicit_header_case_insensitively():
    headers = add_provider_affinity_header(
        headers={"x-conversation-id": "explicit-session"},
        hangarllm_params={
            "hangarllm_session_id": "session-123",
            "provider_affinity_header": "X-Conversation-Id",
        },
    )

    assert headers == {"x-conversation-id": "explicit-session"}


@pytest.mark.parametrize("session_id", ["session\r", "session\n", "session\0"])
def test_add_provider_affinity_header_rejects_control_characters(session_id: str):
    with pytest.raises(ValueError, match="session_id cannot contain HTTP header control characters"):
        add_provider_affinity_header(
            headers={},
            hangarllm_params={
                "hangarllm_session_id": session_id,
                "provider_affinity_header": "X-Conversation-Id",
            },
        )


def test_add_provider_affinity_header_does_nothing_without_config_or_session():
    assert add_provider_affinity_header({}, {"hangarllm_session_id": "session-123"}) == {}
    assert (
        add_provider_affinity_header(
            {},
            {"provider_affinity_header": "X-Conversation-Id"},
        )
        == {}
    )

