from types import MappingProxyType
from typing import Final

import pytest
from pydantic import ValidationError

import hangarllm
from hangarllm.rust_bridge.host.routes.responses import connection_defaults, map_failure, response
from hangarllm.types.llms.openai import ResponsesAPIResponse


def test_response_validates_into_the_public_responses_model() -> None:
    built: Final = response(
        MappingProxyType(
            {
                "id": "resp_native",
                "object": "response",
                "created_at": 1,
                "model": "gpt-4o",
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "id": "msg_native",
                        "role": "assistant",
                        "status": "completed",
                        "content": [{"type": "output_text", "text": "native", "annotations": []}],
                    }
                ],
            }
        )
    )

    assert isinstance(built, ResponsesAPIResponse)
    assert built.id == "resp_native"
    assert built.output[0].content[0].text == "native"


def test_response_rejects_a_payload_missing_required_fields() -> None:
    with pytest.raises(ValidationError):
        response(MappingProxyType({"object": "response"}))


@pytest.mark.parametrize(
    ("global_key", "provider_key", "expected"),
    (
        ("global", "provider", "global"),
        (None, "provider", "provider"),
        ("", "provider", "provider"),
        (None, None, None),
    ),
)
def test_connection_defaults_preserve_openai_precedence(
    monkeypatch: pytest.MonkeyPatch, global_key: str | None, provider_key: str | None, expected: str | None
) -> None:
    monkeypatch.setattr(hangarllm, "api_key", global_key)
    monkeypatch.setattr(hangarllm, "openai_key", provider_key)
    monkeypatch.setattr(hangarllm, "api_base", "https://configured.invalid/v1")
    assert connection_defaults("openai") == (expected, hangarllm.api_base)


@pytest.mark.parametrize(("global_key", "expected"), (("global", "global"), (None, None)))
def test_connection_defaults_keep_the_openai_key_away_from_openrouter(
    monkeypatch: pytest.MonkeyPatch, global_key: str | None, expected: str | None
) -> None:
    monkeypatch.setattr(hangarllm, "api_key", global_key)
    monkeypatch.setattr(hangarllm, "openai_key", "openai-only")
    monkeypatch.setattr(hangarllm, "api_base", None)
    assert connection_defaults("openrouter") == (expected, None)


class _UpstreamFailure(Exception):
    headers: Final = ()


@pytest.mark.parametrize(
    ("api_base", "base_url", "expected"),
    (
        (None, "https://alias.invalid/v1", "https://alias.invalid/v1"),
        ("", "https://alias.invalid/v1", "https://alias.invalid/v1"),
        ("https://base.invalid/v1", "https://alias.invalid/v1", "https://base.invalid/v1"),
    ),
)
def test_failure_preserves_the_explicit_endpoint(api_base: str | None, base_url: str, expected: str) -> None:
    upstream: Final = _UpstreamFailure(429, '{"error":{"message":"rate limited"}}')
    mapped: Final = map_failure(upstream, {"model": "openai/test-model", "api_base": api_base, "base_url": base_url})
    assert isinstance(mapped, hangarllm.RateLimitError)
    assert str(mapped.response.request.url) == expected
    assert mapped.__context__ is upstream
